from flask import Flask
import pytest
from routes.server_routes import server_routes

def test_basic():
    """Basic test to ensure testing works"""
    assert True

def test_server_routes_blueprint():
    """Test that server_routes blueprint exists"""
    assert server_routes.name == 'server_routes'

def test_server_routes_prefix():
    """Test that server_routes has correct url_prefix"""
    app = Flask(__name__)
    app.register_blueprint(server_routes)
    assert server_routes.url_prefix == None  # Blueprint gets prefix from parent 