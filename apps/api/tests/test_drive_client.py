"""Unit tests for Google Drive client module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from drive_client import build_service, list_files, move_item, DriveClientError


class TestDriveClient:
    """Test cases for Drive client functions."""

    @patch('drive_client.build')
    @patch('drive_client.Credentials')
    def test_build_service_success(self, mock_credentials, mock_build):
        """Test successful service building."""
        # Arrange
        mock_creds_instance = Mock()
        mock_credentials.return_value = mock_creds_instance
        mock_service = Mock()
        mock_build.return_value = mock_service
        
        user_credentials = {
            'access_token': 'test_token',
            'refresh_token': 'test_refresh',
            'client_id': 'test_client_id',
            'client_secret': 'test_client_secret'
        }
        
        # Act
        result = build_service(user_credentials)
        
        # Assert
        assert result == mock_service
        mock_credentials.assert_called_once()
        mock_build.assert_called_once_with('drive', 'v3', credentials=mock_creds_instance)

    def test_build_service_failure(self):
        """Test service building failure."""
        # Arrange
        user_credentials = {}
        
        # Act & Assert
        with pytest.raises(DriveClientError):
            build_service(user_credentials)

    @patch('drive_client.time.sleep')
    def test_list_files_success(self, mock_sleep):
        """Test successful file listing."""
        # Arrange
        mock_service = Mock()
        mock_service.files.return_value.list.return_value.execute.return_value = {
            'files': [
                {'id': '1', 'name': 'test1.txt'},
                {'id': '2', 'name': 'test2.txt'}
            ],
            'nextPageToken': None
        }
        
        # Act
        result = list_files(mock_service)
        
        # Assert
        assert len(result) == 2
        assert result[0]['id'] == '1'
        assert result[1]['id'] == '2'

    @patch('drive_client.time.sleep')
    def test_list_files_with_pagination(self, mock_sleep):
        """Test file listing with pagination."""
        # Arrange
        mock_service = Mock()
        mock_service.files.return_value.list.return_value.execute.side_effect = [
            {
                'files': [{'id': '1', 'name': 'test1.txt'}],
                'nextPageToken': 'token1'
            },
            {
                'files': [{'id': '2', 'name': 'test2.txt'}],
                'nextPageToken': None
            }
        ]
        
        # Act
        result = list_files(mock_service)
        
        # Assert
        assert len(result) == 2
        assert result[0]['id'] == '1'
        assert result[1]['id'] == '2'

    def test_move_item_success(self):
        """Test successful file move."""
        # Arrange
        mock_service = Mock()
        mock_service.files.return_value.get.return_value.execute.return_value = {
            'parents': ['old_parent']
        }
        mock_service.files.return_value.update.return_value.execute.return_value = {
            'id': 'file_id',
            'name': 'test.txt',
            'parents': ['new_parent']
        }
        
        # Act
        result = move_item(mock_service, 'file_id', 'new_parent')
        
        # Assert
        assert result['id'] == 'file_id'
        mock_service.files.return_value.update.assert_called_once()

    def test_move_item_failure(self):
        """Test file move failure."""
        # Arrange
        mock_service = Mock()
        mock_service.files.return_value.get.side_effect = Exception("API Error")
        
        # Act & Assert
        with pytest.raises(DriveClientError):
            move_item(mock_service, 'file_id', 'new_parent') 