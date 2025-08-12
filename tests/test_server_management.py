"""
Tests for server management endpoints (list servers, server status, etc.)
"""
import pytest
import json
from unittest.mock import Mock, patch
from datetime import datetime
from app import app


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestListServersEndpoint:
    """Tests for the GET /api/server/ endpoint."""
    
    @patch('routes.server_routes.KubernetesService')
    def test_list_servers_empty(self, mock_k8s_service, client):
        """Test listing servers when no servers exist."""
        # Mock empty deployments list
        mock_service_instance = Mock()
        mock_deployments = Mock()
        mock_deployments.items = []
        mock_service_instance.apps_api.list_deployment_for_all_namespaces.return_value = mock_deployments
        mock_k8s_service.return_value = mock_service_instance
        
        response = client.get('/api/server/')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['servers'] == []
        assert data['total_count'] == 0
    
    @patch('routes.server_routes.KubernetesService')
    def test_list_servers_single_running(self, mock_k8s_service, client):
        """Test listing servers with one running server."""
        # Mock Kubernetes service
        mock_service_instance = Mock()
        
        # Mock deployment
        mock_deployment = Mock()
        mock_deployment.metadata.labels = {"app": "test-server"}
        mock_deployment.metadata.namespace = "default"
        mock_deployment.metadata.creation_timestamp = datetime.fromisoformat("2023-01-01T00:00:00")
        mock_deployment.status.ready_replicas = 1
        mock_deployment.spec.replicas = 1
        
        mock_deployments = Mock()
        mock_deployments.items = [mock_deployment]
        mock_service_instance.apps_api.list_deployment_for_all_namespaces.return_value = mock_deployments
        
        # Mock service with external IP
        mock_service = Mock()
        mock_service.status.load_balancer.ingress = [Mock(ip="20.1.2.3")]
        mock_service.spec.ports = [Mock(port=25565)]
        mock_service_instance.core_api.read_namespaced_service.return_value = mock_service
        
        mock_k8s_service.return_value = mock_service_instance
        
        response = client.get('/api/server/')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['total_count'] == 1
        assert len(data['servers']) == 1
        
        server = data['servers'][0]
        assert server['server_id'] == 'test-server'
        assert server['namespace'] == 'default'
        assert server['status'] == 'running'
        assert server['replicas']['ready'] == 1
        assert server['replicas']['desired'] == 1
        assert server['connection_info']['external_ip'] == '20.1.2.3'
        assert server['connection_info']['port'] == 25565
        assert server['connection_info']['dns_name'] == 'test-server-dns.eastus.cloudapp.azure.com'
    
    @patch('routes.server_routes.KubernetesService')
    def test_list_servers_multiple_states(self, mock_k8s_service, client):
        """Test listing servers with different states."""
        mock_service_instance = Mock()
        
        # Running server
        running_server = Mock()
        running_server.metadata.labels = {"app": "server-1"}
        running_server.metadata.namespace = "default"
        running_server.metadata.creation_timestamp = datetime.fromisoformat("2023-01-01T00:00:00")
        running_server.status.ready_replicas = 1
        running_server.spec.replicas = 1
        
        # Paused server (0 replicas)
        paused_server = Mock()
        paused_server.metadata.labels = {"app": "server-2"}
        paused_server.metadata.namespace = "default"
        paused_server.metadata.creation_timestamp = datetime.fromisoformat("2023-01-01T01:00:00")
        paused_server.status.ready_replicas = 0
        paused_server.spec.replicas = 0
        
        # Starting server
        starting_server = Mock()
        starting_server.metadata.labels = {"app": "server-3"}
        starting_server.metadata.namespace = "default"
        starting_server.metadata.creation_timestamp = datetime.fromisoformat("2023-01-01T02:00:00")
        starting_server.status.ready_replicas = 0
        starting_server.spec.replicas = 1
        
        mock_deployments = Mock()
        mock_deployments.items = [running_server, paused_server, starting_server]
        mock_service_instance.apps_api.list_deployment_for_all_namespaces.return_value = mock_deployments
        
        # Mock services (some might not exist)
        def mock_read_service(name, namespace):
            if "server-1" in name:
                service = Mock()
                service.status.load_balancer.ingress = [Mock(ip="20.1.2.3")]
                service.spec.ports = [Mock(port=25565)]
                return service
            else:
                raise Exception("Service not found")
        
        mock_service_instance.core_api.read_namespaced_service.side_effect = mock_read_service
        mock_k8s_service.return_value = mock_service_instance
        
        response = client.get('/api/server/')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['total_count'] == 3
        
        # Check server states
        servers_by_id = {s['server_id']: s for s in data['servers']}
        
        assert servers_by_id['server-1']['status'] == 'running'
        assert servers_by_id['server-2']['status'] == 'paused'
        assert servers_by_id['server-3']['status'] == 'starting'
        
        # Only running server should have connection info
        assert servers_by_id['server-1']['connection_info']['external_ip'] == '20.1.2.3'
        assert servers_by_id['server-2']['connection_info']['external_ip'] is None
        assert servers_by_id['server-3']['connection_info']['external_ip'] is None
    
    @patch('routes.server_routes.KubernetesService')
    def test_list_servers_k8s_connection_failure(self, mock_k8s_service, client):
        """Test list servers when Kubernetes connection fails."""
        mock_k8s_service.side_effect = Exception("Connection failed")
        
        response = client.get('/api/server/')
        
        assert response.status_code == 500
        data = json.loads(response.data)
        assert 'Kubernetes operation failed' in data['error']
    
    @patch('routes.server_routes.KubernetesService')
    def test_list_servers_skips_invalid_deployments(self, mock_k8s_service, client):
        """Test that deployments without proper labels are skipped."""
        mock_service_instance = Mock()
        
        # Valid deployment
        valid_deployment = Mock()
        valid_deployment.metadata.labels = {"app": "test-server"}
        valid_deployment.metadata.namespace = "default"
        valid_deployment.metadata.creation_timestamp = datetime.fromisoformat("2023-01-01T00:00:00")
        valid_deployment.status.ready_replicas = 1
        valid_deployment.spec.replicas = 1
        
        # Invalid deployment (no app label)
        invalid_deployment = Mock()
        invalid_deployment.metadata.labels = {}
        invalid_deployment.metadata.namespace = "default"
        
        # Invalid deployment (no namespace)
        no_namespace_deployment = Mock()
        no_namespace_deployment.metadata.labels = {"app": "test"}
        no_namespace_deployment.metadata.namespace = None
        
        mock_deployments = Mock()
        mock_deployments.items = [valid_deployment, invalid_deployment, no_namespace_deployment]
        mock_service_instance.apps_api.list_deployment_for_all_namespaces.return_value = mock_deployments
        
        # Mock service
        mock_service = Mock()
        mock_service.status.load_balancer.ingress = []
        mock_service.spec.ports = [Mock(port=25565)]
        mock_service_instance.core_api.read_namespaced_service.return_value = mock_service
        
        mock_k8s_service.return_value = mock_service_instance
        
        response = client.get('/api/server/')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Should only return the valid deployment
        assert data['total_count'] == 1
        assert data['servers'][0]['server_id'] == 'test-server'


class TestServerStatusEndpoint:
    """Tests for the GET /api/server/status/<server_id> endpoint."""
    
    @patch('routes.server_routes.KubernetesService')
    def test_get_server_status_running(self, mock_k8s_service, client):
        """Test getting status of a running server."""
        mock_service_instance = Mock()
        
        # Mock deployment
        mock_deployment = Mock()
        mock_deployment.metadata.namespace = "default"
        mock_deployment.metadata.creation_timestamp = datetime.fromisoformat("2023-01-01T00:00:00")
        mock_deployment.status.ready_replicas = 1
        mock_deployment.status.available_replicas = 1
        mock_deployment.spec.replicas = 1
        # Create a proper mock container with resources
        mock_container = Mock()
        mock_container.image = "gameregistry.azurecr.io/minecraft-server:latest"
        mock_container.resources = {
            "requests": {"cpu": "4000m", "memory": "8192Mi"},
            "limits": {"cpu": "4000m", "memory": "8192Mi"}
        }
        mock_deployment.spec.template.spec.containers = [mock_container]
        
        mock_deployments = Mock()
        mock_deployments.items = [mock_deployment]
        mock_service_instance.apps_api.list_deployment_for_all_namespaces.return_value = mock_deployments
        
        # Mock service
        mock_service = Mock()
        mock_service.status.load_balancer.ingress = [Mock(ip="20.1.2.3")]
        mock_service.spec.ports = [Mock(port=25565)]
        mock_service.spec.type = "LoadBalancer"
        mock_service_instance.core_api.read_namespaced_service.return_value = mock_service
        
        # Mock pods
        mock_pod = Mock()
        mock_pod.metadata.name = "test-server-12345-abcde"
        mock_pod.metadata.creation_timestamp = datetime.fromisoformat("2023-01-01T00:00:00")
        mock_pod.status.phase = "Running"
        mock_container_status = Mock()
        mock_container_status.ready = True
        mock_container_status.restart_count = 0
        mock_container_status.state.waiting = None
        mock_container_status.state.terminated = None
        mock_pod.status.container_statuses = [mock_container_status]
        
        mock_pod_list = Mock()
        mock_pod_list.items = [mock_pod]
        mock_service_instance.core_api.list_namespaced_pod.return_value = mock_pod_list
        
        mock_k8s_service.return_value = mock_service_instance
        
        response = client.get('/api/server/status/test-server')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['server_id'] == 'test-server'
        assert data['namespace'] == 'default'
        assert data['status'] == 'running'
        assert data['replicas']['ready'] == 1
        assert data['replicas']['desired'] == 1
        assert data['connection_info']['external_ip'] == '20.1.2.3'
        assert data['connection_info']['port'] == 25565
        assert data['image'] == 'gameregistry.azurecr.io/minecraft-server:latest'
        assert len(data['pods']) == 1
        assert data['pods'][0]['name'] == 'test-server-12345-abcde'
        assert data['pods'][0]['ready'] is True
    
    @patch('routes.server_routes.KubernetesService')
    def test_get_server_status_not_found(self, mock_k8s_service, client):
        """Test getting status of non-existent server."""
        mock_service_instance = Mock()
        
        # No deployments found
        mock_deployments = Mock()
        mock_deployments.items = []
        mock_service_instance.apps_api.list_deployment_for_all_namespaces.return_value = mock_deployments
        
        mock_k8s_service.return_value = mock_service_instance
        
        response = client.get('/api/server/status/nonexistent-server')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['error'] == 'Server not found'
        assert 'nonexistent-server' in data['details']
    
    @patch('routes.server_routes.KubernetesService')
    def test_get_server_status_paused(self, mock_k8s_service, client):
        """Test getting status of a paused server."""
        mock_service_instance = Mock()
        
        # Mock paused deployment (0 replicas)
        mock_deployment = Mock()
        mock_deployment.metadata.namespace = "default"
        mock_deployment.metadata.creation_timestamp = datetime.fromisoformat("2023-01-01T00:00:00")
        mock_deployment.status.ready_replicas = 0
        mock_deployment.status.available_replicas = 0
        mock_deployment.spec.replicas = 0
        # Create a proper mock container 
        mock_container = Mock()
        mock_container.image = "minecraft:latest"
        mock_container.resources = {"requests": {"cpu": "2000m", "memory": "4096Mi"}}
        mock_deployment.spec.template.spec.containers = [mock_container]
        
        mock_deployments = Mock()
        mock_deployments.items = [mock_deployment]
        mock_service_instance.apps_api.list_deployment_for_all_namespaces.return_value = mock_deployments
        
        # Service exists but no pods
        mock_service = Mock()
        mock_service.status.load_balancer.ingress = [Mock(ip="20.1.2.3")]
        mock_service.spec.ports = [Mock(port=25565)]
        mock_service.spec.type = "LoadBalancer"
        mock_service_instance.core_api.read_namespaced_service.return_value = mock_service
        
        # No pods running
        mock_pod_list = Mock()
        mock_pod_list.items = []
        mock_service_instance.core_api.list_namespaced_pod.return_value = mock_pod_list
        
        mock_k8s_service.return_value = mock_service_instance
        
        response = client.get('/api/server/status/paused-server')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['server_id'] == 'paused-server'
        assert data['status'] == 'paused'
        assert data['replicas']['ready'] == 0
        assert data['replicas']['desired'] == 0
        assert len(data['pods']) == 0
    
    @patch('routes.server_routes.KubernetesService')
    def test_get_server_status_k8s_connection_failure(self, mock_k8s_service, client):
        """Test server status when Kubernetes connection fails."""
        mock_k8s_service.side_effect = Exception("Connection failed")
        
        response = client.get('/api/server/status/test-server')
        
        assert response.status_code == 500
        data = json.loads(response.data)
        assert 'Kubernetes operation failed' in data['error']
    
    @patch('routes.server_routes.KubernetesService')
    def test_get_server_status_service_not_ready(self, mock_k8s_service, client):
        """Test server status when service exists but no external IP."""
        mock_service_instance = Mock()
        
        # Mock deployment
        mock_deployment = Mock()
        mock_deployment.metadata.namespace = "default"
        mock_deployment.metadata.creation_timestamp = datetime.fromisoformat("2023-01-01T00:00:00")
        mock_deployment.status.ready_replicas = 0
        mock_deployment.status.available_replicas = 0
        mock_deployment.spec.replicas = 1
        # Create a proper mock container 
        mock_container = Mock()
        mock_container.image = "minecraft:latest"
        mock_container.resources = {"requests": {"cpu": "2000m", "memory": "4096Mi"}}
        mock_deployment.spec.template.spec.containers = [mock_container]
        
        mock_deployments = Mock()
        mock_deployments.items = [mock_deployment]
        mock_service_instance.apps_api.list_deployment_for_all_namespaces.return_value = mock_deployments
        
        # Service exists but no IP assigned yet
        mock_service = Mock()
        mock_service.status.load_balancer.ingress = None
        mock_service.spec.ports = [Mock(port=25565)]
        mock_service.spec.type = "LoadBalancer"
        mock_service_instance.core_api.read_namespaced_service.return_value = mock_service
        
        mock_pod_list = Mock()
        mock_pod_list.items = []
        mock_service_instance.core_api.list_namespaced_pod.return_value = mock_pod_list
        
        mock_k8s_service.return_value = mock_service_instance
        
        response = client.get('/api/server/status/starting-server')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['server_id'] == 'starting-server'
        assert data['status'] == 'starting'
        assert data['connection_info']['external_ip'] is None
        assert data['connection_info']['port'] == 25565


class TestEndpointIntegration:
    """Integration tests for multiple endpoints working together."""
    
    @patch('routes.server_routes.KubernetesService')
    def test_list_then_get_status(self, mock_k8s_service, client):
        """Test listing servers then getting detailed status for one."""
        mock_service_instance = Mock()
        
        # Mock deployment for list endpoint
        mock_deployment = Mock()
        mock_deployment.metadata.labels = {"app": "test-server"}
        mock_deployment.metadata.namespace = "default"
        mock_deployment.metadata.creation_timestamp = datetime.fromisoformat("2023-01-01T00:00:00")
        mock_deployment.status.ready_replicas = 1
        mock_deployment.status.available_replicas = 1
        mock_deployment.spec.replicas = 1
        # Create a proper mock container 
        mock_container = Mock()
        mock_container.image = "minecraft:latest"
        mock_container.resources = {"requests": {"cpu": "2000m", "memory": "4096Mi"}}
        mock_deployment.spec.template.spec.containers = [mock_container]
        
        mock_deployments = Mock()
        mock_deployments.items = [mock_deployment]
        mock_service_instance.apps_api.list_deployment_for_all_namespaces.return_value = mock_deployments
        
        # Mock service
        mock_service = Mock()
        mock_service.status.load_balancer.ingress = [Mock(ip="20.1.2.3")]
        mock_service.spec.ports = [Mock(port=25565)]
        mock_service.spec.type = "LoadBalancer"
        mock_service_instance.core_api.read_namespaced_service.return_value = mock_service
        
        # Mock pods for status endpoint
        mock_pod_list = Mock()
        mock_pod_list.items = []
        mock_service_instance.core_api.list_namespaced_pod.return_value = mock_pod_list
        
        mock_k8s_service.return_value = mock_service_instance
        
        # Test list endpoint
        list_response = client.get('/api/server/')
        assert list_response.status_code == 200
        list_data = json.loads(list_response.data)
        
        # Get server_id from list
        server_id = list_data['servers'][0]['server_id']
        
        # Test status endpoint
        status_response = client.get(f'/api/server/status/{server_id}')
        assert status_response.status_code == 200
        status_data = json.loads(status_response.data)
        
        # Verify consistency
        assert status_data['server_id'] == server_id
        assert status_data['connection_info']['external_ip'] == list_data['servers'][0]['connection_info']['external_ip']