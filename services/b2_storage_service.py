from b2sdk.v2 import B2Api, InMemoryAccountInfo
import os
import logging
import tempfile

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
            # The ls() method returns a generator of tuples, we need to handle it differently
            file_list = []
            for file_version_info, _ in self.bucket.ls(f"{server_id}/"):
                file_list.append(file_version_info.file_name)
            return file_list
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
        """Update or create a file"""
        try:
            full_path = f"{server_id}/{file_path}"
            data = content.encode('utf-8')
            
            # Create a temporary file with the content
            with tempfile.NamedTemporaryFile() as temp_file:
                temp_file.write(data)
                temp_file.flush()
                
                # Upload the file to B2
                self.bucket.upload_local_file(
                    local_file=temp_file.name,
                    file_name=full_path
                )
                logger.info(f"Successfully uploaded {file_path} for server {server_id}")
        except Exception as e:
            logger.error(f"Failed to update file {file_path}: {str(e)}")
            raise
