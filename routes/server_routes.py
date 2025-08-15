from flask import Blueprint, request, jsonify
from services.kubernetes_service import KubernetesService
from services.b2_storage_service import B2StorageService
from utils.validators import StartServerSchema, StopServerSchema, PauseServerSchema, ResumeServerSchema
from config.logging_config import ErrorHandler
from marshmallow import ValidationError
import logging
import time

server_routes = Blueprint("server_routes", __name__)

# Example Game Configuration (mocked; replace with DB lookup later)
GAME_PACKAGES = {
    "standard": {
        "cpu": 4000,  # 4 cores
        "memory": 8192,  # 8 GB in MiB
        "image": "gameregistry.azurecr.io/minecraft-server:latest",
        "port": 25565,
        "env_vars": {
            "EULA": "TRUE",
            "MEMORY": "5G",
            "SERVER_NAME": "Azure Test Minecraft Server",
        }
        # "volume": {
        #     "name": "data-volume",
        #     "mount_path": "/data",
        #     "azure_file": {
        #         "secretName": "azure-secret",  # Secret storing account key
        #         "shareName": "data",  # File share name
        #         "readOnly": False
        #     }
        # }
    }
}

logger = logging.getLogger(__name__)

@server_routes.route("/", methods=["GET"])
def list_servers():
    """List all running game servers across all namespaces."""
    logger.info("=== List Servers Request Received ===")
    
    try:
        # Initialize Kubernetes service
        try:
            k8s_service = KubernetesService()
        except Exception as k8s_error:
            error_response, status_code = ErrorHandler.handle_kubernetes_error(logger, k8s_error)
            return jsonify(error_response), status_code
        
        # Get all deployments with game server labels
        deployments = k8s_service.apps_api.list_deployment_for_all_namespaces(
            label_selector="app"
        )
        
        servers = []
        for deployment in deployments.items:
            # Extract server information
            server_id = deployment.metadata.labels.get("app")
            namespace = deployment.metadata.namespace
            
            # Skip non-game server deployments (safety check)
            if not server_id or not namespace:
                continue
                
            # Get service information for IP/port
            service_info = None
            try:
                service = k8s_service.core_api.read_namespaced_service(
                    name=f"{server_id}-svc",
                    namespace=namespace
                )
                
                external_ip = None
                if service.status.load_balancer and service.status.load_balancer.ingress:
                    external_ip = service.status.load_balancer.ingress[0].ip
                    
                service_info = {
                    "external_ip": external_ip,
                    "port": service.spec.ports[0].port if service.spec.ports else None,
                    "dns_name": f"{server_id}-dns.eastus.cloudapp.azure.com" if external_ip else None
                }
            except Exception:
                # Service might not exist or be ready yet
                service_info = {"external_ip": None, "port": None, "dns_name": None}
            
            # Determine server status
            ready_replicas = deployment.status.ready_replicas or 0
            desired_replicas = deployment.spec.replicas or 0
            
            if ready_replicas == desired_replicas and ready_replicas > 0:
                status = "running"
            elif ready_replicas == 0 and desired_replicas == 0:
                status = "paused" 
            elif ready_replicas < desired_replicas:
                status = "starting"
            else:
                status = "unknown"
            
            server_info = {
                "server_id": server_id,
                "namespace": namespace,
                "status": status,
                "replicas": {
                    "ready": ready_replicas,
                    "desired": desired_replicas
                },
                "created": deployment.metadata.creation_timestamp.isoformat() if deployment.metadata.creation_timestamp else None,
                "connection_info": service_info
            }
            servers.append(server_info)
        
        logger.info(f"Found {len(servers)} game servers")
        return jsonify({
            "servers": servers,
            "total_count": len(servers)
        }), 200
        
    except Exception as e:
        error_response = ErrorHandler.log_and_format_error(logger, e, "List servers")
        return jsonify(error_response), 500

@server_routes.route("/status/<server_id>", methods=["GET"])
def get_server_status(server_id):
    """Get detailed status information for a specific game server."""
    logger.info(f"=== Get Server Status Request: {server_id} ===")
    
    try:
        # Initialize Kubernetes service
        try:
            k8s_service = KubernetesService()
        except Exception as k8s_error:
            error_response, status_code = ErrorHandler.handle_kubernetes_error(logger, k8s_error)
            return jsonify(error_response), status_code
        
        # Search for deployment across all namespaces
        deployments = k8s_service.apps_api.list_deployment_for_all_namespaces(
            label_selector=f"app={server_id}"
        )
        
        if not deployments.items:
            logger.warning(f"Server {server_id} not found")
            return jsonify({
                "error": "Server not found",
                "details": f"No deployment found with server_id: {server_id}",
                "server_id": server_id
            }), 404
        
        # Get the first (should be only) deployment
        deployment = deployments.items[0]
        namespace = deployment.metadata.namespace
        
        # Get detailed deployment information
        ready_replicas = deployment.status.ready_replicas or 0
        desired_replicas = deployment.spec.replicas or 0
        available_replicas = deployment.status.available_replicas or 0
        
        # Determine detailed status
        if ready_replicas == desired_replicas and ready_replicas > 0:
            status = "running"
        elif ready_replicas == 0 and desired_replicas == 0:
            status = "paused"
        elif ready_replicas < desired_replicas:
            status = "starting"
        elif available_replicas < ready_replicas:
            status = "degraded"
        else:
            status = "unknown"
        
        # Get service information
        service_info = {"external_ip": None, "port": None, "dns_name": None}
        try:
            service = k8s_service.core_api.read_namespaced_service(
                name=f"{server_id}-svc",
                namespace=namespace
            )
            
            external_ip = None
            if service.status.load_balancer and service.status.load_balancer.ingress:
                external_ip = service.status.load_balancer.ingress[0].ip
                
            service_info = {
                "external_ip": external_ip,
                "port": service.spec.ports[0].port if service.spec.ports else None,
                "dns_name": f"{server_id}-dns.eastus.cloudapp.azure.com" if external_ip else None,
                "service_type": service.spec.type
            }
        except Exception as service_error:
            logger.warning(f"Could not get service info for {server_id}: {str(service_error)}")
        
        # Get pod information
        pods = []
        try:
            pod_list = k8s_service.core_api.list_namespaced_pod(
                namespace=namespace,
                label_selector=f"app={server_id}"
            )
            
            for pod in pod_list.items:
                pod_info = {
                    "name": pod.metadata.name,
                    "status": pod.status.phase,
                    "ready": False,
                    "restarts": 0,
                    "created": pod.metadata.creation_timestamp.isoformat() if pod.metadata.creation_timestamp else None
                }
                
                # Check container status
                if pod.status.container_statuses:
                    container = pod.status.container_statuses[0]
                    pod_info["ready"] = container.ready
                    pod_info["restarts"] = container.restart_count
                    
                    if container.state.waiting:
                        pod_info["status"] = f"waiting: {container.state.waiting.reason}"
                    elif container.state.terminated:
                        pod_info["status"] = f"terminated: {container.state.terminated.reason}"
                
                pods.append(pod_info)
                
        except Exception as pod_error:
            logger.warning(f"Could not get pod info for {server_id}: {str(pod_error)}")
        
        # Get resource information
        container_spec = deployment.spec.template.spec.containers[0] if deployment.spec.template.spec.containers else None
        resources = {
            "requests": {},
            "limits": {}
        }
        
        if container_spec and hasattr(container_spec, 'resources') and container_spec.resources:
            if isinstance(container_spec.resources, dict):
                if container_spec.resources.get("requests"):
                    resources["requests"] = container_spec.resources["requests"]
                if container_spec.resources.get("limits"):
                    resources["limits"] = container_spec.resources["limits"]
        
        server_status = {
            "server_id": server_id,
            "namespace": namespace,
            "status": status,
            "replicas": {
                "desired": desired_replicas,
                "ready": ready_replicas,
                "available": available_replicas
            },
            "created": deployment.metadata.creation_timestamp.isoformat() if deployment.metadata.creation_timestamp else None,
            "connection_info": service_info,
            "pods": pods,
            "resources": resources,
            "image": container_spec.image if container_spec and hasattr(container_spec, 'image') else "unknown"
        }
        
        logger.info(f"Retrieved status for server {server_id}: {status}")
        return jsonify(server_status), 200
        
    except Exception as e:
        error_response = ErrorHandler.log_and_format_error(logger, e, "Get server status")
        return jsonify(error_response), 500

@server_routes.route("/start-server", methods=["POST"])
def start_server():
    logger.info("=== Start Server Request Received ===")
    
    try:
        # Validate request data
        try:
            data = request.get_json(force=True)
        except Exception:
            logger.error("No JSON data received")
            return jsonify({"error": "No data provided"}), 400
            
        if data is None:
            logger.error("No JSON data received")
            return jsonify({"error": "No data provided"}), 400
        
        # Use marshmallow for validation
        try:
            validated_data = StartServerSchema().load(data)
            package = validated_data['package']
            server_id = validated_data['server_id']
            namespace = validated_data['namespace']
            logger.info(f"Request validated: server_id={server_id}, package={package}, namespace={namespace}")
        except ValidationError as e:
            error_response, status_code = ErrorHandler.handle_validation_error(logger, e)
            return jsonify(error_response), status_code

        config = GAME_PACKAGES[package]
        logger.info(f"Using package configuration: {config}")
        
        # Initialize Kubernetes service
        try:
            k8s_service = KubernetesService()
        except Exception as k8s_error:
            error_response, status_code = ErrorHandler.handle_kubernetes_error(logger, k8s_error)
            return jsonify(error_response), status_code
            
        # Initialize B2 storage and check for existing files
        b2_service = B2StorageService()
        existing_files = b2_service.list_files(server_id)
        
        # Only create default files if this is a new server
        if not existing_files:
            logger.info(f"New server detected. Creating default files for {server_id}")
            default_files = {
                "server.properties": "server-name=My Minecraft Server\ndifficulty=normal\ngamemode=survival",
                "ops.json": "[]",
                "whitelist.json": "[]",
                "banned-players.json": "[]",
                "banned-ips.json": "[]"
            }
            for filename, content in default_files.items():
                b2_service.update_file(server_id, filename, content)
        else:
            logger.info(f"Existing server detected. Will restore files for {server_id}: {existing_files}")
        
        # Deploy the server
        KubernetesService.deploy_game_server(
            server_id=server_id,
            namespace=namespace,
            image=config["image"],
            cpu=config["cpu"],
            memory=config["memory"],
            port=config["port"],
            env_vars=config["env_vars"],
            # TODO: Add volume mount for B2 files
        )
        
        # After deploying the server
        node_ip, node_port = KubernetesService.create_game_service(
            server_id=server_id,
            namespace=namespace,
            port=config["port"]
        )
        
        return jsonify({
            "message": f"Server {server_id} for package {package} is starting...",
            "files_restored": bool(existing_files),
            "existing_files": existing_files if existing_files else [],
            "connection_info": {
                "ip": node_ip,
                "port": node_port
            }
        }), 200
        
    except Exception as e:
        error_response = ErrorHandler.log_and_format_error(logger, e, "Start server")
        return jsonify(error_response), 500

@server_routes.route("/stop-server", methods=["POST"])
def stop_server():
    data = request.json
    server_id = data.get("server_id")
    namespace = data.get("namespace", "default")

    try:
        logger.info(f"Stopping server {server_id} in namespace {namespace}")
        
        # Save files to B2 before stopping
        b2_service = B2StorageService()
        
        # Get files from running container
        files_to_save = [
            "server.properties",
            "ops.json",
            "whitelist.json",
            "banned-players.json",
            "banned-ips.json"
        ]
        
        # Copy files from pod
        file_contents = KubernetesService.copy_files_from_pod(
            server_id=server_id,
            namespace=namespace,
            file_paths=files_to_save
        )
        
        # Save files to B2
        saved_files = []
        for file_path, content in file_contents.items():
            if content:
                b2_service.update_file(server_id, file_path, content)
                saved_files.append(file_path)
                logger.info(f"Saved file {file_path} for server {server_id}")
        
        # TODO: Add special handling for world directory
        logger.warning("World directory backup not implemented yet")
        
        # Stop the server
        KubernetesService.delete_deployment(server_id, namespace)
        
        return jsonify({
            "message": f"Server {server_id} stopped successfully",
            "files_saved": saved_files
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to stop server: {str(e)}")
        return jsonify({"error": f"Failed to stop server: {str(e)}"}), 500

@server_routes.route("/pause-server", methods=["POST"])
def pause_server():
    data = request.json
    server_id = data.get("server_id")
    namespace = data.get("namespace", "default")

    try:
        logger.info(f"=== PAUSING SERVER {server_id} IN NAMESPACE {namespace} ===")
        
        # Save files to B2 before pausing
        logger.info(f"Initializing B2 storage service for file backup")
        b2_service = B2StorageService()
        
        # Get files from running container
        files_to_save = [
            "server.properties",
            "ops.json",
            "whitelist.json",
            "banned-players.json",
            "banned-ips.json"
        ]
        logger.info(f"Preparing to save files: {files_to_save}")
        
        # Copy files from pod
        logger.info(f"Copying files from pod {server_id}")
        file_contents = KubernetesService.copy_files_from_pod(
            server_id=server_id,
            namespace=namespace,
            file_paths=files_to_save
        )
        
        # Log the files that were found
        found_files = list(file_contents.keys())
        logger.info(f"Found {len(found_files)} files in pod: {found_files}")
        
        # Save files to B2
        saved_files = []
        for file_path, content in file_contents.items():
            if content:
                logger.info(f"Saving file {file_path} ({len(content)} bytes) to B2")
                b2_service.update_file(server_id, file_path, content)
                saved_files.append(file_path)
                logger.info(f"Successfully saved file {file_path} for server {server_id}")
            else:
                logger.warning(f"File {file_path} has no content, skipping")
        
        # Backup world directory
        logger.info(f"Backing up world directory for server {server_id}")
        try:
            # Create a temporary directory for the world backup
            import tempfile
            import shutil
            import os
            import subprocess
            from kubernetes.stream import stream
            
            with tempfile.TemporaryDirectory() as temp_dir:
                world_backup_path = os.path.join(temp_dir, "world.tar.gz")
                
                # Get the pod name
                service = KubernetesService()
                pod_list = service.core_api.list_namespaced_pod(
                    namespace=namespace,
                    label_selector=f"app={server_id}"
                )
                
                if not pod_list.items:
                    logger.error(f"No pods found for server {server_id}")
                    raise ValueError(f"No pods found for server {server_id}")
                
                pod_name = pod_list.items[0].metadata.name
                
                # First, check if the world directory exists and has content
                logger.info(f"Checking if world directory exists in pod {pod_name}")
                exec_command = ['ls', '-la', '/data/world']
                resp = stream(
                    service.core_api.connect_get_namespaced_pod_exec,
                    pod_name,
                    namespace,
                    command=exec_command,
                    stderr=True, stdin=False,
                    stdout=True, tty=False,
                    _preload_content=False
                )
                resp.run_forever()
                world_ls_output = resp.read_all()
                logger.info(f"World directory contents: {world_ls_output}")
                
                # Create a tar archive of the world directory in the pod
                logger.info(f"Creating tar archive of world directory in pod {pod_name}")
                exec_command = ['tar', '-czf', '/tmp/world.tar.gz', '-C', '/data', 'world']
                resp = stream(
                    service.core_api.connect_get_namespaced_pod_exec,
                    pod_name,
                    namespace,
                    command=exec_command,
                    stderr=True, stdin=False,
                    stdout=True, tty=False,
                    _preload_content=False
                )
                resp.run_forever()
                tar_output = resp.read_all()
                logger.info(f"Tar command output: {tar_output}")
                
                # Check if the tar file was created and its size
                logger.info(f"Checking if tar file was created")
                exec_command = ['ls', '-la', '/tmp/world.tar.gz']
                resp = stream(
                    service.core_api.connect_get_namespaced_pod_exec,
                    pod_name,
                    namespace,
                    command=exec_command,
                    stderr=True, stdin=False,
                    stdout=True, tty=False,
                    _preload_content=False
                )
                resp.run_forever()
                tar_ls_output = resp.read_all()
                logger.info(f"Tar file info: {tar_ls_output}")
                
                # Copy the tar file from the pod to the local temp directory
                logger.info(f"Copying world backup from pod to local temp directory")
                
                # Use the Kubernetes API to copy the file - use base64 encoding to handle binary data safely
                exec_command = ['sh', '-c', 'base64 /tmp/world.tar.gz']
                resp = stream(
                    service.core_api.connect_get_namespaced_pod_exec,
                    pod_name,
                    namespace,
                    command=exec_command,
                    stderr=True, stdin=False,
                    stdout=True, tty=False,
                    _preload_content=False
                )
                
                # Wait for the command to complete
                resp.run_forever()
                
                # Get the base64 encoded output
                world_data_base64 = resp.read_all()
                logger.info(f"Base64 output length: {len(world_data_base64)} characters")
                logger.info(f"First 100 chars of base64: {world_data_base64[:100]}")
                
                # Decode the base64 data to get the binary content
                import base64
                try:
                    world_data = base64.b64decode(world_data_base64)
                    logger.info(f"Successfully decoded base64 data: {len(world_data)} bytes")
                except Exception as decode_error:
                    logger.error(f"Failed to decode base64 data: {decode_error}")
                    raise
                
                # Write the binary data to the local file
                with open(world_backup_path, 'wb') as f:
                    f.write(world_data)
                
                # Check if the file was created and has content
                if os.path.exists(world_backup_path) and os.path.getsize(world_backup_path) > 0:
                    logger.info(f"World backup created: {world_backup_path} ({os.path.getsize(world_backup_path)} bytes)")
                    
                    # Upload the world backup to B2
                    logger.info(f"Uploading world backup to B2")
                    with open(world_backup_path, 'rb') as f:
                        world_data = f.read()
                    
                    # Convert binary data to base64 for storage
                    import base64
                    world_data_base64 = base64.b64encode(world_data).decode('utf-8')
                    
                    # Store the world data in B2
                    b2_service.update_file(server_id, "world.tar.gz.b64", world_data_base64, is_binary=False)
                    saved_files.append("world.tar.gz.b64")
                    logger.info(f"Successfully uploaded world backup for server {server_id}")
                else:
                    logger.error(f"Failed to create world backup: {world_backup_path}")
            
        except Exception as world_backup_error:
            logger.error(f"Failed to backup world directory: {str(world_backup_error)}")
        
        # Pause the server by scaling to 0 replicas
        logger.info(f"Scaling deployment {server_id} to 0 replicas")
        KubernetesService.scale_deployment(server_id, namespace, 0)
        logger.info(f"Deployment {server_id} scaled to 0 replicas")
        
        logger.info(f"=== SERVER {server_id} PAUSED SUCCESSFULLY ===")
        logger.info(f"Saved {len(saved_files)} files: {saved_files}")
        
        return jsonify({
            "message": f"Server {server_id} paused successfully",
            "files_saved": saved_files,
            "status": "paused"
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to pause server: {str(e)}")
        return jsonify({"error": f"Failed to pause server: {str(e)}"}), 500

@server_routes.route("/resume-server", methods=["POST"])
def resume_server():
    data = request.json
    server_id = data.get("server_id")
    namespace = data.get("namespace", "default")

    try:
        logger.info(f"=== RESUMING SERVER {server_id} IN NAMESPACE {namespace} ===")
        
        # Scale the deployment back to 1 replica
        logger.info(f"Scaling deployment {server_id} to 1 replica")
        KubernetesService.scale_deployment(server_id, namespace, 1)
        
        # Get the service information
        service_name = f"{server_id}-svc"
        logger.info(f"Getting service information for {service_name}")
        service = KubernetesService()
        svc = service.core_api.read_namespaced_service(service_name, namespace)
        
        # Wait for the pod to be ready
        logger.info("Waiting for pod to be ready...")
        ready = False
        for attempt in range(12):  # 60-second timeout
            pod_list = service.core_api.list_namespaced_pod(
                namespace=namespace,
                label_selector=f"app={server_id}"
            )
            if pod_list.items and pod_list.items[0].status.phase == "Running":
                ready = True
                logger.info(f"Pod is running after {attempt + 1} attempts")
                break
            logger.info(f"Waiting for pod to be ready... Attempt {attempt + 1}/12")
            time.sleep(5)
        
        if not ready:
            logger.warning("Pod not ready after 60 seconds, but continuing...")
        
        # Get the pod name for file restoration
        pod_list = service.core_api.list_namespaced_pod(
            namespace=namespace,
            label_selector=f"app={server_id}"
        )
        
        restored_files = []
        if pod_list.items:
            pod_name = pod_list.items[0].metadata.name
            logger.info(f"Found pod {pod_name} for file restoration")
            
            # Restore files from B2 storage
            logger.info(f"Initializing B2 storage service for file restoration")
            b2_service = B2StorageService()
            files_to_restore = b2_service.list_files(server_id)
            
            logger.info(f"Found {len(files_to_restore)} files to restore: {files_to_restore}")
            
            # Wait a bit for the container to initialize
            logger.info("Waiting for container to initialize...")
            time.sleep(10)  # Increased from 5 to 10 seconds
            
            # Import the stream module for WebSocket connections
            from kubernetes.stream import stream
            
            # Try to list files in the pod to verify it's ready
            try:
                logger.info(f"Verifying pod is ready by listing files in /data directory")
                exec_command = ['ls', '-la', '/data']
                resp = stream(
                    service.core_api.connect_get_namespaced_pod_exec,
                    pod_name,
                    namespace,
                    command=exec_command,
                    stderr=True, stdin=False,
                    stdout=True, tty=False,
                    _preload_content=False
                )
                
                # Wait for the command to complete
                resp.run_forever()
                
                # Get the output
                output = resp.read_all()
                logger.info(f"Files in /data directory before restoration: {output}")
            except Exception as e:
                logger.warning(f"Could not list files in /data directory: {str(e)}")
            
            # First, check if we have a world backup to restore
            world_backup_file = "world.tar.gz.b64"
            has_world_backup = world_backup_file in files_to_restore
            
            # If we have a world backup, restore it first
            if has_world_backup:
                try:
                    logger.info(f"Found world backup, restoring it first")
                    
                    # Get the world backup from B2
                    logger.info(f"Getting world backup from B2")
                    world_data_base64 = b2_service.get_file(server_id, world_backup_file, is_binary=True)
                    
                    # Decode the base64 data
                    import base64
                    import tempfile
                    import os
                    
                    # If we read the file as binary, we need to decode it to string first
                    if isinstance(world_data_base64, bytes):
                        world_data_base64 = world_data_base64.decode('utf-8')
                    
                    world_data = base64.b64decode(world_data_base64)
                    
                    # Create a temporary file for the world backup
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.tar.gz') as temp_file:
                        temp_file_path = temp_file.name
                        temp_file.write(world_data)
                    
                    logger.info(f"World backup saved to temporary file: {temp_file_path} ({len(world_data)} bytes)")
                    
                    # Copy the world backup to the pod
                    logger.info(f"Copying world backup to pod {pod_name}")
                    
                    # First, copy the tar file to the pod
                    with open(temp_file_path, 'rb') as f:
                        world_data = f.read()
                    
                    # Create the /tmp directory in the pod if it doesn't exist
                    exec_command = ['mkdir', '-p', '/tmp']
                    resp = stream(
                        service.core_api.connect_get_namespaced_pod_exec,
                        pod_name,
                        namespace,
                        command=exec_command,
                        stderr=True, stdin=False,
                        stdout=True, tty=False,
                        _preload_content=False
                    )
                    resp.run_forever()
                    
                    # Write the world backup to the pod using base64 encoding to handle binary data safely
                    # First encode the binary data as base64
                    world_data_base64 = base64.b64encode(world_data).decode('utf-8')
                    
                    exec_command = ['sh', '-c', 'base64 -d > /tmp/world.tar.gz']
                    resp = stream(
                        service.core_api.connect_get_namespaced_pod_exec,
                        pod_name,
                        namespace,
                        command=exec_command,
                        stderr=True, stdin=True,
                        stdout=True, tty=False,
                        _preload_content=False
                    )
                    
                    # Write the base64 encoded data to stdin
                    resp.write_stdin(world_data_base64)
                    
                    # Close stdin to signal we're done writing
                    resp.close()
                    
                    logger.info(f"World backup copied to pod, extracting it")
                    
                    # Extract the world backup
                    exec_command = ['sh', '-c', 'rm -rf /data/world && tar -xzf /tmp/world.tar.gz -C /data']
                    resp = stream(
                        service.core_api.connect_get_namespaced_pod_exec,
                        pod_name,
                        namespace,
                        command=exec_command,
                        stderr=True, stdin=False,
                        stdout=True, tty=False,
                        _preload_content=False
                    )
                    
                    # Wait for the command to complete
                    resp.run_forever()
                    
                    # Get the output
                    output = resp.read_all()
                    logger.info(f"World extraction output: {output}")
                    
                    # Clean up the temporary file
                    os.unlink(temp_file_path)
                    
                    restored_files.append(world_backup_file)
                    logger.info(f"Successfully restored world backup for server {server_id}")
                    
                except Exception as world_restore_error:
                    logger.error(f"Failed to restore world backup: {str(world_restore_error)}")
            
            # Now restore the configuration files
            for file_path in files_to_restore:
                try:
                    # Skip directory entries and the world backup (already handled)
                    if file_path.endswith('/') or file_path == world_backup_file:
                        logger.info(f"Skipping file: {file_path}")
                        continue
                    
                    # Get the file content from B2
                    logger.info(f"Getting content for file {file_path} from B2")
                    content = b2_service.get_file(server_id, file_path)
                    logger.info(f"Retrieved {len(content)} bytes for file {file_path}")
                    
                    # Write the file to the pod
                    # For Minecraft server, files are in /data directory
                    full_path = f"/data/{file_path}"
                    logger.info(f"Preparing to write file to {full_path} in pod {pod_name}")
                    
                    # Create directory if needed
                    if '/' in file_path:
                        dir_path = '/'.join(full_path.split('/')[:-1])
                        logger.info(f"Creating directory {dir_path} in pod")
                        exec_command = ['mkdir', '-p', dir_path]
                        resp = stream(
                            service.core_api.connect_get_namespaced_pod_exec,
                            pod_name,
                            namespace,
                            command=exec_command,
                            stderr=True, stdin=False,
                            stdout=True, tty=False,
                            _preload_content=False
                        )
                        resp.run_forever()
                    
                    # Write file content to the pod
                    # We need to use stdin to write the file
                    logger.info(f"Writing content to {full_path} in pod")
                    exec_command = ['sh', '-c', f'cat > {full_path}']
                    resp = stream(
                        service.core_api.connect_get_namespaced_pod_exec,
                        pod_name,
                        namespace,
                        command=exec_command,
                        stderr=True, stdin=True,
                        stdout=True, tty=False,
                        _preload_content=False
                    )
                    
                    # Write the content to stdin
                    resp.write_stdin(content)
                    
                    # Close stdin to signal we're done writing
                    resp.close()
                    
                    restored_files.append(file_path)
                    logger.info(f"Successfully restored file {file_path} to pod {pod_name}")
                    
                except Exception as e:
                    logger.error(f"Failed to restore file {file_path}: {str(e)}")
            
            # Verify files were restored
            try:
                logger.info(f"Verifying files were restored by listing /data directory")
                exec_command = ['ls', '-la', '/data']
                resp = stream(
                    service.core_api.connect_get_namespaced_pod_exec,
                    pod_name,
                    namespace,
                    command=exec_command,
                    stderr=True, stdin=False,
                    stdout=True, tty=False,
                    _preload_content=False
                )
                
                # Wait for the command to complete
                resp.run_forever()
                
                # Get the output
                output = resp.read_all()
                logger.info(f"Files in /data directory after restoration: {output}")
            except Exception as e:
                logger.warning(f"Could not list files in /data directory after restoration: {str(e)}")
        
        # Get the external IP and port
        external_ip = None
        port = None
        if svc.status.load_balancer.ingress:
            external_ip = svc.status.load_balancer.ingress[0].ip
            port = svc.spec.ports[0].port
        
        logger.info(f"=== SERVER {server_id} RESUMED SUCCESSFULLY ===")
        logger.info(f"Connection info: IP={external_ip}, Port={port}")
        logger.info(f"Restored {len(restored_files)} files: {restored_files}")
        
        return jsonify({
            "message": f"Server {server_id} resumed successfully",
            "status": "running",
            "files_restored": restored_files,
            "connection_info": {
                "ip": external_ip,
                "port": port
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to resume server: {str(e)}")
        return jsonify({"error": f"Failed to resume server: {str(e)}"}), 500
