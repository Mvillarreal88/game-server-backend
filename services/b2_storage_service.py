from b2sdk.v2 import B2Api, InMemoryAccountInfo
import os
import logging

logger = logging.getLogger(__name__)

class B2StorageService:
    def __init__(self):
        self.info = InMemoryAccountInfo()
        self.api = B2Api(self.info)
        self.api.authorize_account("production", 
            os.getenv('B2_KEY_ID'),
            os.getenv('B2_APP_KEY')
        )
        self.bucket = self.api.get_bucket_by_name(os.getenv('B2_BUCKET_NAME', 'game-servers'))
        logger.info(f"Initialized B2 storage service with bucket: {self.bucket.name}")

    def list_files(self, server_id):
        """List all files for a server"""
        try:
            files = self.bucket.ls(f"{server_id}/")
            return [file.file_name for file in files]
        except Exception as e:
            logger.error(f"Failed to list files for server {server_id}: {str(e)}")
            raise

    def get_file(self, server_id, file_path):
        """Get file content"""
        try:
            full_path = f"{server_id}/{file_path}"
            download = self.bucket.download_file_by_name(full_path)
            with download.save_to() as file:
                return file.read().decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to get file {file_path}: {str(e)}")
            raise

    def update_file(self, server_id, file_path, content):
        """Update file content"""
        try:
            full_path = f"{server_id}/{file_path}"
            self.bucket.upload_bytes(
                content.encode('utf-8'),
                full_path
            )
        except Exception as e:
            logger.error(f"Failed to update file {file_path}: {str(e)}")
            raise
