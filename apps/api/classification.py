"""AI-powered file classification service using OpenAI GPT-4."""

import json
import uuid
from typing import Dict, List, Any
import openai
import structlog
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

class FileMetadata(BaseModel):
    """File metadata model for classification."""
    id: str
    name: str
    mimeType: str
    parents: List[str] = []
    createdTime: str
    modifiedTime: str
    size: str = "0"

class FolderStructure(BaseModel):
    """Folder structure proposal model."""
    name: str
    description: str
    children: List['FolderStructure'] = []
    files: List[str] = []  # File IDs that should go in this folder

class ClassificationProposal(BaseModel):
    """Complete classification proposal."""
    root_folders: List[FolderStructure]
    orphaned_files: List[str]  # File IDs that couldn't be classified
    reasoning: str

# Update forward references
FolderStructure.model_rebuild()

def propose_structure(metadata: List[Dict], user_preferences: Dict = None) -> Dict:
    """
    Generate a folder structure proposal using OpenAI GPT-4.
    
    Args:
        metadata: List of file metadata dictionaries
        user_preferences: User preferences for classification
        
    Returns:
        Dictionary containing the proposed folder structure
    """
    try:
        # Prepare the prompt
        prompt = _build_classification_prompt(metadata, user_preferences)
        
        # Call OpenAI API
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",  # Use mini for cost optimization
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert file organization assistant. Your task is to analyze file metadata and propose a logical folder structure that groups related files together."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,  # Lower temperature for more consistent results
            max_tokens=2000
        )
        
        # Parse the response
        content = response.choices[0].message.content
        proposal = _parse_classification_response(content, metadata)
        
        logger.info("Successfully generated classification proposal", 
                   file_count=len(metadata),
                   folder_count=len(proposal.get('root_folders', [])))
        
        return proposal
        
    except Exception as e:
        logger.error("Failed to generate classification proposal", error=str(e))
        raise Exception(f"Classification failed: {str(e)}")

def _build_classification_prompt(metadata: List[Dict], user_preferences: Dict = None) -> str:
    """Build the classification prompt for OpenAI."""
    
    # Filter files based on user preferences
    filtered_metadata = _filter_metadata(metadata, user_preferences)
    
    # Create a summary of file types and patterns
    file_summary = _create_file_summary(filtered_metadata)
    
    prompt = f"""
Please analyze the following Google Drive files and propose a logical folder structure.

File Summary:
{file_summary}

File Details (first 50 files for analysis):
{json.dumps(filtered_metadata[:50], indent=2)}

User Preferences:
- Ignore MIME types: {user_preferences.get('ignore_mime', []) if user_preferences else []}
- Ignore large files: {user_preferences.get('ignore_large', False) if user_preferences else False}

Please provide a JSON response with the following structure:
{{
  "root_folders": [
    {{
      "name": "Folder Name",
      "description": "Brief description of what goes in this folder",
      "children": [
        {{
          "name": "Subfolder Name",
          "description": "Description",
          "children": [],
          "files": ["file_id1", "file_id2"]
        }}
      ],
      "files": ["file_id3", "file_id4"]
    }}
  ],
  "orphaned_files": ["file_id5", "file_id6"],
  "reasoning": "Brief explanation of the proposed structure"
}}

Guidelines:
1. Group files by type, purpose, or project
2. Use clear, descriptive folder names
3. Consider file extensions and MIME types
4. Keep the structure simple and intuitive
5. Don't create too many nested levels (max 3-4)
6. Include only the file IDs in the response, not full metadata

Please respond with only the JSON structure, no additional text.
"""
    
    return prompt

def _filter_metadata(metadata: List[Dict], user_preferences: Dict = None) -> List[Dict]:
    """Filter metadata based on user preferences."""
    if not user_preferences:
        return metadata
    
    filtered = []
    ignore_mime = user_preferences.get('ignore_mime', [])
    ignore_large = user_preferences.get('ignore_large', False)
    max_size = user_preferences.get('max_file_size_mb', 100) * 1024 * 1024  # Convert to bytes
    
    for file in metadata:
        # Skip ignored MIME types
        if file.get('mimeType') in ignore_mime:
            continue
        
        # Skip large files if configured
        if ignore_large and file.get('size'):
            try:
                file_size = int(file['size'])
                if file_size > max_size:
                    continue
            except (ValueError, TypeError):
                pass
        
        filtered.append(file)
    
    return filtered

def _create_file_summary(metadata: List[Dict]) -> str:
    """Create a summary of file types and patterns."""
    mime_counts = {}
    extension_counts = {}
    
    for file in metadata:
        mime_type = file.get('mimeType', 'unknown')
        mime_counts[mime_type] = mime_counts.get(mime_type, 0) + 1
        
        name = file.get('name', '')
        if '.' in name:
            ext = name.split('.')[-1].lower()
            extension_counts[ext] = extension_counts.get(ext, 0) + 1
    
    summary = f"Total files: {len(metadata)}\n\n"
    summary += "Top MIME types:\n"
    for mime, count in sorted(mime_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        summary += f"  {mime}: {count}\n"
    
    summary += "\nTop file extensions:\n"
    for ext, count in sorted(extension_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        summary += f"  .{ext}: {count}\n"
    
    return summary

def _parse_classification_response(content: str, metadata: List[Dict]) -> Dict:
    """Parse the OpenAI response into a structured proposal."""
    try:
        # Extract JSON from the response
        start_idx = content.find('{')
        end_idx = content.rfind('}') + 1
        
        if start_idx == -1 or end_idx == 0:
            raise ValueError("No JSON found in response")
        
        json_str = content[start_idx:end_idx]
        proposal = json.loads(json_str)
        
        # Validate the structure
        if not isinstance(proposal, dict):
            raise ValueError("Invalid proposal structure")
        
        if 'root_folders' not in proposal:
            raise ValueError("Missing root_folders in proposal")
        
        # Validate file IDs exist in metadata
        all_file_ids = {file['id'] for file in metadata}
        _validate_file_ids(proposal, all_file_ids)
        
        return proposal
        
    except json.JSONDecodeError as e:
        logger.error("Failed to parse JSON response", error=str(e), content=content)
        raise ValueError(f"Invalid JSON response: {str(e)}")
    except Exception as e:
        logger.error("Failed to parse classification response", error=str(e))
        raise ValueError(f"Failed to parse response: {str(e)}")

def _validate_file_ids(proposal: Dict, valid_file_ids: set):
    """Validate that all file IDs in the proposal exist in the metadata."""
    def check_folder(folder):
        for file_id in folder.get('files', []):
            if file_id not in valid_file_ids:
                logger.warning(f"Invalid file ID in proposal: {file_id}")
        
        for child in folder.get('children', []):
            check_folder(child)
    
    for folder in proposal.get('root_folders', []):
        check_folder(folder)
    
    for file_id in proposal.get('orphaned_files', []):
        if file_id not in valid_file_ids:
            logger.warning(f"Invalid file ID in orphaned files: {file_id}")

def summarize_large_file_list(metadata: List[Dict], max_files: int = 4000) -> List[Dict]:
    """
    Summarize large file lists to reduce OpenAI API costs.
    
    Args:
        metadata: List of file metadata
        max_files: Maximum number of files to include in analysis
        
    Returns:
        Summarized metadata list
    """
    if len(metadata) <= max_files:
        return metadata
    
    # Group files by MIME type and sample from each group
    mime_groups = {}
    for file in metadata:
        mime_type = file.get('mimeType', 'unknown')
        if mime_type not in mime_groups:
            mime_groups[mime_type] = []
        mime_groups[mime_type].append(file)
    
    # Calculate how many files to sample from each group
    total_groups = len(mime_groups)
    files_per_group = max(1, max_files // total_groups)
    
    summarized = []
    for mime_type, files in mime_groups.items():
        # Sample files from each group
        if len(files) <= files_per_group:
            summarized.extend(files)
        else:
            # Take a representative sample
            step = len(files) // files_per_group
            sampled = files[::step][:files_per_group]
            summarized.extend(sampled)
    
    logger.info("Summarized large file list", 
               original_count=len(metadata),
               summarized_count=len(summarized))
    
    return summarized 