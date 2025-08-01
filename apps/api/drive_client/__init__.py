"""Google Drive API client wrapper with retry logic and error handling."""

import time
from typing import Dict, List, Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import structlog

logger = structlog.get_logger(__name__)

# If modifying these scopes, delete the file token.json.
SCOPES = [
    'https://www.googleapis.com/auth/drive.metadata.readonly',
    'https://www.googleapis.com/auth/drive.file'
]

class DriveClientError(Exception):
    """Custom exception for Drive API errors."""
    pass

def build_service(user_credentials: Dict) -> 'Resource':
    """
    Build and return a Google Drive service object.
    
    Args:
        user_credentials: Dictionary containing OAuth credentials
        
    Returns:
        Google Drive service resource
        
    Raises:
        DriveClientError: If service creation fails
    """
    try:
        credentials = Credentials(
            token=user_credentials.get('access_token'),
            refresh_token=user_credentials.get('refresh_token'),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=user_credentials.get('client_id'),
            client_secret=user_credentials.get('client_secret'),
            scopes=SCOPES
        )
        
        # Refresh token if expired
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        
        service = build('drive', 'v3', credentials=credentials)
        return service
        
    except Exception as e:
        logger.error("Failed to build Drive service", error=str(e))
        raise DriveClientError(f"Failed to build Drive service: {str(e)}")

def list_files(service: 'Resource', page_size: int = 1000, page_token: Optional[str] = None, mime_type: Optional[str] = None, max_results: Optional[int] = None) -> Dict:
    """
    List files in Google Drive with pagination and retry logic.
    
    Args:
        service: Google Drive service resource
        page_size: Number of files to fetch per request
        page_token: Token for pagination
        mime_type: Filter by MIME type (e.g., 'application/vnd.google-apps.folder' for folders)
        max_results: Maximum number of results to return
        
    Returns:
        Dictionary with 'files' list and 'nextPageToken' if available
        
    Raises:
        DriveClientError: If API calls fail after retries
    """
    max_retries = 3
    base_delay = 1
    
    try:
        retry_count = 0
        while retry_count < max_retries:
            try:
                # Build query parameters
                query_params = {
                    'pageSize': page_size,
                    'fields': "nextPageToken, files(id, name, mimeType, parents, createdTime, modifiedTime, size, webViewLink)"
                }
                
                if page_token:
                    query_params['pageToken'] = page_token
                
                if mime_type:
                    query_params['q'] = f"mimeType='{mime_type}'"
                
                # Call the Drive v3 API
                results = service.files().list(**query_params).execute()
                
                items = results.get('files', [])
                
                # Apply max_results limit if specified
                if max_results and len(items) > max_results:
                    items = items[:max_results]
                    # Remove nextPageToken if we're limiting results
                    results.pop('nextPageToken', None)
                
                logger.info("Successfully listed files", count=len(items))
                return results
                
            except HttpError as error:
                retry_count += 1
                if error.resp.status in [403, 429]:  # Rate limit or quota exceeded
                    if retry_count < max_retries:
                        delay = base_delay * (2 ** (retry_count - 1))  # Exponential backoff
                        logger.warning(f"Rate limited, retrying in {delay}s", retry_count=retry_count)
                        time.sleep(delay)
                        continue
                    else:
                        logger.error("Max retries exceeded for rate limit", error=str(error))
                        raise DriveClientError(f"Rate limit exceeded after {max_retries} retries")
                else:
                    logger.error("Drive API error", error=str(error))
                    raise DriveClientError(f"Drive API error: {str(error)}")
                    
            except Exception as e:
                logger.error("Unexpected error listing files", error=str(e))
                raise DriveClientError(f"Unexpected error: {str(e)}")
                    
    except Exception as e:
        logger.error("Failed to list files", error=str(e))
        raise DriveClientError(f"Failed to list files: {str(e)}")

def move_item(service: 'Resource', file_id: str, new_parent_id: str) -> Dict:
    """
    Move a file or folder to a new parent folder.
    
    Args:
        service: Google Drive service resource
        file_id: ID of the file/folder to move
        new_parent_id: ID of the new parent folder
        
    Returns:
        Updated file metadata
        
    Raises:
        DriveClientError: If move operation fails
    """
    try:
        # Get the current parents
        file = service.files().get(fileId=file_id, fields='parents').execute()
        previous_parents = ",".join(file.get('parents', []))
        
        # Move the file to the new folder
        file = service.files().update(
            fileId=file_id,
            addParents=new_parent_id,
            removeParents=previous_parents,
            fields='id, name, parents'
        ).execute()
        
        logger.info("Successfully moved file", file_id=file_id, new_parent_id=new_parent_id)
        return file
        
    except HttpError as error:
        logger.error("Failed to move file", file_id=file_id, error=str(error))
        raise DriveClientError(f"Failed to move file: {str(error)}")
    except Exception as e:
        logger.error("Unexpected error moving file", file_id=file_id, error=str(e))
        raise DriveClientError(f"Unexpected error moving file: {str(e)}")

def get_file_metadata(service: 'Resource', file_id: str) -> Dict:
    """
    Get detailed metadata for a specific file.
    
    Args:
        service: Google Drive service resource
        file_id: ID of the file
        
    Returns:
        File metadata dictionary
        
    Raises:
        DriveClientError: If metadata retrieval fails
    """
    try:
        file = service.files().get(
            fileId=file_id,
            fields="id, name, mimeType, parents, createdTime, modifiedTime, size, webViewLink, description"
        ).execute()
        
        return file
        
    except HttpError as error:
        logger.error("Failed to get file metadata", file_id=file_id, error=str(error))
        raise DriveClientError(f"Failed to get file metadata: {str(error)}")
    except Exception as e:
        logger.error("Unexpected error getting file metadata", file_id=file_id, error=str(e))
        raise DriveClientError(f"Unexpected error getting file metadata: {str(e)}")

def create_folder(service: 'Resource', name: str, parent_id: Optional[str] = None) -> Dict:
    """
    Create a new folder in Google Drive.
    
    Args:
        service: Google Drive service resource
        name: Name of the folder
        parent_id: ID of the parent folder (optional)
        
    Returns:
        Created folder metadata
        
    Raises:
        DriveClientError: If folder creation fails
    """
    try:
        folder_metadata = {
            'name': name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        
        if parent_id:
            folder_metadata['parents'] = [parent_id]
        
        folder = service.files().create(
            body=folder_metadata,
            fields='id, name, parents'
        ).execute()
        
        logger.info("Successfully created folder", folder_id=folder['id'], name=name)
        return folder
        
    except HttpError as error:
        logger.error("Failed to create folder", name=name, error=str(error))
        raise DriveClientError(f"Failed to create folder: {str(error)}")
    except Exception as e:
        logger.error("Unexpected error creating folder", name=name, error=str(e))
        raise DriveClientError(f"Unexpected error creating folder: {str(e)}") 