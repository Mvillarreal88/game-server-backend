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
        self.bucket = self.api.get_bucket_by_name(os.getenv('B2_BUCKET_NAME', 'mc-test-v1'))
        logger.info(f"Initialized B2 storage service with bucket: {self.bucket.name}")

    def list_files(self, server_id):
        """List all files for a server"""
        try:
            # The ls() method returns a generator of tuples, we need to handle it differently
            file_list = []
            prefix = f"{server_id}/"
            for file_version_info, _ in self.bucket.ls(prefix):
                # Remove the server_id prefix to get just the file name
                if file_version_info.file_name.startswith(prefix):
                    relative_path = file_version_info.file_name[len(prefix):]
                    if relative_path:  # Skip empty paths
                        file_list.append(relative_path)
                else:
                    # If for some reason the prefix isn't there, add the full name
                    file_list.append(file_version_info.file_name)
            
            logger.info(f"Found {len(file_list)} files for server {server_id}: {file_list}")
            return file_list
        except Exception as e:
            logger.error(f"Failed to list files for server {server_id}: {str(e)}")
            raise

    def get_file(self, server_id, file_path):
        """Get file content"""
        try:
            # Ensure we have the correct path format
            if file_path.startswith(f"{server_id}/"):
                full_path = file_path
            else:
                full_path = f"{server_id}/{file_path}"
            
            logger.info(f"Getting file {full_path} from B2 bucket")
            download = self.bucket.download_file_by_name(full_path)
            with download.save_to() as file:
                content = file.read().decode('utf-8')
                logger.info(f"Successfully read file {file_path} ({len(content)} bytes)")
                return content
        except Exception as e:
            logger.error(f"Failed to get file {file_path}: {str(e)}")
            raise

    def update_file(self, server_id, file_path, content):
        """Update or create a file"""
        try:
            full_path = f"{server_id}/{file_path}"
            data = content.encode('utf-8')
            
            # Create a temporary file with the content
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(data)
                temp_file.flush()
                
                logger.info(f"Uploading file {full_path} to B2 bucket {self.bucket.name}")
                
                # Upload the file to B2
                file_info = self.bucket.upload_local_file(
                    local_file=temp_file.name,
                    file_name=full_path
                )
                
                # Debug the file_info object to see what attributes are available
                logger.info(f"File info type: {type(file_info)}")
                logger.info(f"File info attributes: {dir(file_info)}")
                
                # Use file_version_id instead of id if available, or handle both cases
                file_id = getattr(file_info, 'id_', None) or getattr(file_info, 'id', None) or getattr(file_info, 'file_id', None) or getattr(file_info, 'file_version_id', 'unknown')
                
                logger.info(f"Successfully uploaded {file_path} for server {server_id}. File ID: {file_id}")
                
                # Clean up temp file
                os.unlink(temp_file.name)
                
        except Exception as e:
            logger.error(f"Failed to update file {file_path} for server {server_id}: {str(e)}")
            raise
