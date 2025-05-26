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
                logger.info(f"Using provided full path: {full_path}")
            else:
                full_path = f"{server_id}/{file_path}"
                logger.info(f"Constructed full path: {full_path}")
            
            logger.info(f"Getting file {full_path} from B2 bucket {self.bucket.name}")
            
            try:
                # Create a temporary file to save the downloaded content
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    temp_file_path = temp_file.name
                
                # Download the file to the temporary location
                download = self.bucket.download_file_by_name(full_path)
                download.save_to(temp_file_path)
                
                # Read the content from the temporary file
                with open(temp_file_path, 'r') as f:
                    content = f.read()
                
                # Clean up the temporary file
                os.unlink(temp_file_path)
                
                logger.info(f"Successfully read file {file_path} ({len(content)} bytes)")
                return content
            except Exception as download_error:
                logger.error(f"Error downloading file {full_path}: {str(download_error)}")
                
                # Try listing files to see what's available
                logger.info(f"Listing available files with prefix {server_id}/")
                available_files = []
                for file_version_info, _ in self.bucket.ls(f"{server_id}/"):
                    available_files.append(file_version_info.file_name)
                
                logger.info(f"Available files: {available_files}")
                raise
        except Exception as e:
            logger.error(f"Failed to get file {file_path}: {str(e)}")
            raise

    def update_file(self, server_id, file_path, content, is_binary=False):
        """Update or create a file"""
        try:
            full_path = f"{server_id}/{file_path}"
            
            # Handle binary vs text content
            if is_binary:
                data = content
                logger.info(f"Preparing to upload binary file {full_path} ({len(data)} bytes) to B2 bucket {self.bucket.name}")
            else:
                data = content.encode('utf-8')
                logger.info(f"Preparing to upload text file {full_path} ({len(data)} bytes) to B2 bucket {self.bucket.name}")
            
            # Create a temporary file with the content
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(data)
                temp_file.flush()
                temp_file_path = temp_file.name
                
                logger.info(f"Created temporary file at {temp_file_path}")
                
                # Upload the file to B2
                logger.info(f"Uploading file {full_path} to B2 bucket {self.bucket.name}")
                
                try:
                    file_info = self.bucket.upload_local_file(
                        local_file=temp_file_path,
                        file_name=full_path
                    )
                    
                    # Debug the file_info object to see what attributes are available
                    logger.info(f"File info type: {type(file_info)}")
                    logger.debug(f"File info attributes: {dir(file_info)}")
                    
                    # Use file_version_id instead of id if available, or handle both cases
                    file_id = getattr(file_info, 'id_', None) or getattr(file_info, 'id', None) or getattr(file_info, 'file_id', None) or getattr(file_info, 'file_version_id', 'unknown')
                    
                    logger.info(f"Successfully uploaded {file_path} for server {server_id}. File ID: {file_id}")
                except Exception as upload_error:
                    logger.error(f"Error uploading file {full_path}: {str(upload_error)}")
                    raise
                finally:
                    # Clean up temp file
                    logger.debug(f"Cleaning up temporary file {temp_file_path}")
                    os.unlink(temp_file_path)
                
        except Exception as e:
            logger.error(f"Failed to update file {file_path} for server {server_id}: {str(e)}")
            raise
