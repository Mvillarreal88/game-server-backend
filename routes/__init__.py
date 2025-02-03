from flask import Blueprint
from .user_routes import user_routes
from .server_routes import server_routes
from .game_routes import game_routes
from .bucket_routes import bucket_routes

api = Blueprint('api', __name__, url_prefix='/api')

# Register all API route groups
api.register_blueprint(user_routes, url_prefix='/user')
api.register_blueprint(server_routes, url_prefix='/server')
api.register_blueprint(game_routes, url_prefix='/game')
api.register_blueprint(bucket_routes, url_prefix='/bucket')
