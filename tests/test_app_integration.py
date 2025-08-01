"""
Integration tests for the Flask application.
"""
import pytest
import json
from unittest.mock import patch, Mock
from app import app

@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

class TestHealthEndpoints:
    """Tests for health check endpoints."""
    
    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get('/health')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'healthy'
    
    def test_robots_txt(self, client):
        """Test robots.txt endpoint."""
        response = client.get('/robots933456.txt')
        
        assert response.status_code == 200
        assert response.data == b''

class TestStartServerEndpoint:
    """Tests for the start server endpoint."""
    
    def test_start_server_no_data(self, client):
        """Test start server endpoint with no data."""
        response = client.post('/api/server/start-server',
                              content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'No data provided' in data['error']
    
    def test_start_server_invalid_json(self, client):
        """Test start server endpoint with invalid JSON."""
        response = client.post('/api/server/start-server',
                              data='invalid json',
                              content_type='application/json')
        
        assert response.status_code == 400
    
    def test_start_server_missing_fields(self, client):
        """Test start server endpoint with missing required fields."""
        data = {'package': 'standard'}  # Missing server_id
        
        response = client.post('/api/server/start-server',
                              data=json.dumps(data),
                              content_type='application/json')
        
        assert response.status_code == 400
        response_data = json.loads(response.data)
        assert 'error' in response_data
    
    def test_start_server_invalid_server_id(self, client):
        """Test start server endpoint with invalid server ID."""
        data = {
            'package': 'standard',
            'server_id': 'INVALID_SERVER_ID'  # Contains uppercase and underscore
        }
        
        response = client.post('/api/server/start-server',
                              data=json.dumps(data),
                              content_type='application/json')
        
        assert response.status_code == 400
        response_data = json.loads(response.data)
        assert 'Validation failed' in response_data['error']
    
    def test_start_server_invalid_package(self, client):
        """Test start server endpoint with invalid package."""
        data = {
            'package': 'invalid-package',
            'server_id': 'test-server'
        }
        
        response = client.post('/api/server/start-server',
                              data=json.dumps(data),
                              content_type='application/json')
        
        assert response.status_code == 400
        response_data = json.loads(response.data)
        assert 'Validation failed' in response_data['error']
    
    @patch('app.KubernetesService')
    def test_start_server_k8s_connection_failure(self, mock_k8s_service, client):
        """Test start server endpoint with Kubernetes connection failure."""
        # Mock KubernetesService to raise an exception
        mock_k8s_service.side_effect = Exception("Connection failed")
        
        data = {
            'package': 'standard',
            'server_id': 'test-server'
        }
        
        response = client.post('/api/server/start-server',
                              data=json.dumps(data),
                              content_type='application/json')
        
        assert response.status_code == 500
        response_data = json.loads(response.data)
        assert 'Kubernetes operation failed' in response_data['error']
    
    @patch('app.KubernetesService')
    def test_start_server_success(self, mock_k8s_service, client):
        """Test successful start server request."""
        # Mock successful Kubernetes service
        mock_service_instance = Mock()
        mock_service_instance.core_api.list_namespace.return_value.items = ['default', 'kube-system']
        mock_k8s_service.return_value = mock_service_instance
        
        data = {
            'package': 'standard',
            'server_id': 'test-server-001',
            'namespace': 'default'
        }
        
        response = client.post('/api/server/start-server',
                              data=json.dumps(data),
                              content_type='application/json')
        
        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert response_data['success'] is True
        assert response_data['server_id'] == 'test-server-001'
        assert response_data['package'] == 'standard'
        assert response_data['namespace_count'] == 2
    
    @patch('app.KubernetesService')
    def test_start_server_namespace_error(self, mock_k8s_service, client):
        """Test start server with namespace listing error."""
        # Mock Kubernetes service that fails on namespace listing
        mock_service_instance = Mock()
        mock_service_instance.core_api.list_namespace.side_effect = Exception("Access denied")
        mock_k8s_service.return_value = mock_service_instance
        
        data = {
            'package': 'standard',
            'server_id': 'test-server'
        }
        
        response = client.post('/api/server/start-server',
                              data=json.dumps(data),
                              content_type='application/json')
        
        assert response.status_code == 500
        response_data = json.loads(response.data)
        assert 'Kubernetes operation failed' in response_data['error']