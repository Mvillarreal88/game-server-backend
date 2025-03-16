from flask import Blueprint, request, jsonify
from services.kubernetes_service import KubernetesService
from services.b2_storage_service import B2StorageService
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

@server_routes.route("/start-server", methods=["POST"])
def start_server():
    data = request.json
    package = data.get("package")
    server_id = data.get("server_id")
    namespace = data.get("namespace", "default")

    if package not in GAME_PACKAGES:
        return jsonify({"error": f"Invalid package: {package}"}), 400

    config = GAME_PACKAGES[package]
    
    try:
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
        return jsonify({"error": f"Failed to start server: {str(e)}"}), 500


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
        logger.info(f"Pausing server {server_id} in namespace {namespace}")
        
        # Save files to B2 before pausing
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
        
        # Pause the server by scaling to 0 replicas
        KubernetesService.scale_deployment(server_id, namespace, 0)
        
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
            
            for file_path in files_to_restore:
                try:
                    # Skip directory entries
                    if file_path.endswith('/'):
                        logger.info(f"Skipping directory entry: {file_path}")
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
