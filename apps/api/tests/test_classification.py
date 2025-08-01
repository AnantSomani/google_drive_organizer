"""Unit tests for AI classification module."""

import pytest
from unittest.mock import Mock, patch
from classification import (
    propose_structure,
    _filter_metadata,
    _create_file_summary,
    summarize_large_file_list
)


class TestClassification:
    """Test cases for classification functions."""

    def test_filter_metadata_no_preferences(self):
        """Test metadata filtering with no preferences."""
        # Arrange
        metadata = [
            {'id': '1', 'name': 'test1.txt', 'mimeType': 'text/plain', 'size': '1000'},
            {'id': '2', 'name': 'test2.pdf', 'mimeType': 'application/pdf', 'size': '5000'}
        ]
        
        # Act
        result = _filter_metadata(metadata, None)
        
        # Assert
        assert len(result) == 2
        assert result == metadata

    def test_filter_metadata_with_ignore_mime(self):
        """Test metadata filtering with ignored MIME types."""
        # Arrange
        metadata = [
            {'id': '1', 'name': 'test1.txt', 'mimeType': 'text/plain', 'size': '1000'},
            {'id': '2', 'name': 'test2.pdf', 'mimeType': 'application/pdf', 'size': '5000'}
        ]
        preferences = {'ignore_mime': ['application/pdf']}
        
        # Act
        result = _filter_metadata(metadata, preferences)
        
        # Assert
        assert len(result) == 1
        assert result[0]['id'] == '1'

    def test_filter_metadata_with_ignore_large(self):
        """Test metadata filtering with large file ignore."""
        # Arrange
        metadata = [
            {'id': '1', 'name': 'test1.txt', 'mimeType': 'text/plain', 'size': '1000'},
            {'id': '2', 'name': 'test2.pdf', 'mimeType': 'application/pdf', 'size': '104857600'}  # 100MB
        ]
        preferences = {'ignore_large': True, 'max_file_size_mb': 50}
        
        # Act
        result = _filter_metadata(metadata, preferences)
        
        # Assert
        assert len(result) == 1
        assert result[0]['id'] == '1'

    def test_create_file_summary(self):
        """Test file summary creation."""
        # Arrange
        metadata = [
            {'id': '1', 'name': 'test1.txt', 'mimeType': 'text/plain'},
            {'id': '2', 'name': 'test2.txt', 'mimeType': 'text/plain'},
            {'id': '3', 'name': 'test3.pdf', 'mimeType': 'application/pdf'}
        ]
        
        # Act
        result = _create_file_summary(metadata)
        
        # Assert
        assert 'Total files: 3' in result
        assert 'text/plain: 2' in result
        assert 'application/pdf: 1' in result

    def test_summarize_large_file_list_small(self):
        """Test file list summarization with small list."""
        # Arrange
        metadata = [{'id': str(i), 'name': f'test{i}.txt'} for i in range(100)]
        
        # Act
        result = summarize_large_file_list(metadata, max_files=1000)
        
        # Assert
        assert len(result) == 100
        assert result == metadata

    def test_summarize_large_file_list_large(self):
        """Test file list summarization with large list."""
        # Arrange
        metadata = []
        for i in range(1000):
            mime_type = 'text/plain' if i % 2 == 0 else 'application/pdf'
            metadata.append({
                'id': str(i),
                'name': f'test{i}.txt',
                'mimeType': mime_type
            })
        
        # Act
        result = summarize_large_file_list(metadata, max_files=100)
        
        # Assert
        assert len(result) <= 100
        assert len(result) > 0

    @patch('classification.openai.ChatCompletion.create')
    def test_propose_structure_success(self, mock_openai):
        """Test successful structure proposal."""
        # Arrange
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
        {
          "root_folders": [
            {
              "name": "Documents",
              "description": "Document files",
              "children": [],
              "files": ["1", "2"]
            }
          ],
          "orphaned_files": [],
          "reasoning": "Organized by file type"
        }
        '''
        mock_openai.return_value = mock_response
        
        metadata = [
            {'id': '1', 'name': 'test1.txt', 'mimeType': 'text/plain'},
            {'id': '2', 'name': 'test2.txt', 'mimeType': 'text/plain'}
        ]
        
        # Act
        result = propose_structure(metadata)
        
        # Assert
        assert 'root_folders' in result
        assert len(result['root_folders']) == 1
        assert result['root_folders'][0]['name'] == 'Documents'

    @patch('classification.openai.ChatCompletion.create')
    def test_propose_structure_failure(self, mock_openai):
        """Test structure proposal failure."""
        # Arrange
        mock_openai.side_effect = Exception("API Error")
        
        metadata = [{'id': '1', 'name': 'test1.txt', 'mimeType': 'text/plain'}]
        
        # Act & Assert
        with pytest.raises(Exception):
            propose_structure(metadata) 