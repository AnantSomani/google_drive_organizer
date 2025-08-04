import os
import json
import logging
from typing import List, Dict, Optional
from datetime import datetime, timezone
from openai import OpenAI
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class AIService:
    """Service for AI-powered Google Drive organization"""
    
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        self.client = OpenAI(api_key=api_key)
    
    def _prepare_file_data(self, files: List[Dict], folders: List[Dict]) -> str:
        """Prepare file and folder data for LLM analysis"""
        file_data = []
        
        # Add folders
        for folder in folders:
            file_data.append({
                "id": folder.get("id"),
                "name": folder.get("name", "Unknown"),
                "type": "folder",
                "parent": folder.get("parents", [""])[0] if folder.get("parents") else "root"
            })
        
        # Add files
        for file in files:
            file_data.append({
                "id": file.get("id"),
                "name": file.get("name", "Unknown"),
                "type": "file",
                "mime_type": file.get("mimeType", ""),
                "parent": file.get("parents", [""])[0] if file.get("parents") else "root"
            })
        
        return json.dumps(file_data, indent=2)
    
    def _create_analysis_prompt(self, file_data: str) -> str:
        """Create the LLM prompt for drive analysis"""
        return f"""
You are an expert file organizer. Analyze the following Google Drive files and folders and suggest a better organization structure.

Rules:
1. Group related files into logical folders based on name similarity, file types, and common patterns
2. Use clear, descriptive folder names (2-4 words max)
3. Keep folder depth reasonable (max 2 levels deep)
4. Consider file types and naming patterns
5. Don't create too many folders - aim for 5-15 main categories

Files and folders to analyze:
{file_data}

Return a JSON object with this exact structure:
{{
  "proposed_folders": [
    {{
      "name": "folder_name",
      "description": "brief description of what goes here"
    }}
  ],
  "file_moves": [
    {{
      "file_id": "file_id_from_input",
      "file_name": "original_file_name",
      "current_parent": "current_parent_id",
      "proposed_folder": "folder_name_from_proposed_folders"
    }}
  ]
}}

Focus on creating a logical, intuitive structure that would help someone find files quickly.
"""
    
    async def generate_proposal(self, scan_id: str, files: List[Dict], folders: List[Dict]) -> Dict:
        """Generate AI proposal for drive organization"""
        try:
            logger.info(f"Starting AI analysis for scan {scan_id}")
            
            # Prepare data for LLM
            file_data = self._prepare_file_data(files, folders)
            prompt = self._create_analysis_prompt(file_data)
            
            # Call OpenAI
            logger.info(f"Calling OpenAI for scan {scan_id}")
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert file organizer. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                max_tokens=2000,
                temperature=0.3
            )
            
            # Parse response
            result = json.loads(response.choices[0].message.content)
            
            # Create proposal
            proposal = {
                "scan_id": scan_id,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "total_items": len(files) + len(folders),
                "proposed_folders": result.get("proposed_folders", []),
                "file_moves": result.get("file_moves", [])
            }
            
            logger.info(f"AI analysis completed for scan {scan_id}: {len(proposal['proposed_folders'])} folders, {len(proposal['file_moves'])} moves")
            return proposal
            
        except Exception as e:
            logger.error(f"AI analysis failed for scan {scan_id}: {str(e)}")
            raise Exception(f"AI analysis failed: {str(e)}") 