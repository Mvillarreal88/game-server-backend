from flask import Blueprint, request, jsonify
from services.b2_storage_service import B2StorageService
import os
import logging

logger = logging.getLogger(__name__)
bucket_routes = Blueprint("bucket_routes", __name__)

@bucket_routes.route("/test", methods=["GET"])
def test_connection():
    """Test B2 storage connection"""
    try:
        b2_service = B2StorageService()
        return jsonify({
            "status": "success",
            "bucket": b2_service.bucket.name
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bucket_routes.route("/files/<server_id>", methods=["GET"])
def list_files(server_id):
    """List all files for a server"""
    try:
        b2_service = B2StorageService()
        files = b2_service.list_files(server_id)
        return jsonify({"files": files}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bucket_routes.route("/files/<server_id>/<path:file_path>", methods=["GET", "PUT"])
def manage_file(server_id, file_path):
    """Get or update file content"""
    try:
        b2_service = B2StorageService()
        
        if request.method == "GET":
            content = b2_service.get_file(server_id, file_path)
            return jsonify({"content": content}), 200
            
        elif request.method == "PUT":
            content = request.json.get("content")
            if not content:
                return jsonify({"error": "No content provided"}), 400
            b2_service.update_file(server_id, file_path, content)
            return jsonify({"message": "File updated successfully"}), 200
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500
