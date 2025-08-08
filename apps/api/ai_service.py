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
        """Prepare structured data for LLM analysis with folder inventory and root clutter."""
        from datetime import datetime, timezone
        import json
        
        def parse_iso(dt: Optional[str]) -> Optional[datetime]:
            if not dt:
                return None
            try:
                # Handle trailing Z
                return datetime.fromisoformat(dt.replace('Z', '+00:00'))
            except Exception:
                return None

        def sanitize_string(s: str) -> str:
            """Safely sanitize strings for JSON serialization"""
            if not s:
                return ""
            # Remove or replace problematic characters that could break JSON
            s = str(s).replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
            # Remove any other control characters
            s = ''.join(char for char in s if ord(char) >= 32 or char in '\n\r\t')
            return s.strip()

        # Build folder index for path resolution
        folder_by_id = {}
        for f in folders:
            folder_by_id[str(f.get('id', ''))] = {
                'id': str(f.get('id', '')),
                'name': sanitize_string(f.get('name', '')),
                'parent': (f.get('parents') or [None])[0]
            }

        def build_path(folder_id: Optional[str]) -> str:
            parts = []
            current = folder_id
            seen = set()
            while current and current not in seen:
                seen.add(current)
                meta = folder_by_id.get(current)
                if not meta:
                    break
                parts.append(sanitize_string(meta['name']) or 'Untitled')
                current = meta.get('parent')
            return 'My Drive/' + '/'.join(reversed(parts)) if parts else 'My Drive'

        now = datetime.now(timezone.utc)

        # Existing folders summary
        folder_stats = {}
        for f in folders:
            fid = str(f.get('id', ''))
            folder_stats[fid] = {
                'id': fid,
                'name': sanitize_string(f.get('name', '')),
                'path': build_path(fid),
                'file_count': 0,
                'recent_count': 0,
                'sample_files': []
            }

        # Files: derive signals
        unorganized_files = []
        for file in files:
            fid = str(file.get('id', ''))
            name = sanitize_string(file.get('name', 'Unknown'))
            mime = sanitize_string(file.get('mimeType', ''))
            parents = file.get('parents', []) or []
            parent_id = parents[0] if parents else None
            path = build_path(parent_id)
            created = parse_iso(file.get('createdTime'))
            modified = parse_iso(file.get('modifiedTime')) or created or now
            age_days = int((now - (created or now)).total_seconds() // 86400)
            last_active_days = int((now - (modified or now)).total_seconds() // 86400)
            ext = name.split('.')[-1].lower() if '.' in name else ''
            in_root = (parent_id is None) or (path == 'My Drive')

            # Update folder stats
            if parent_id and parent_id in folder_stats:
                fs = folder_stats[parent_id]
                fs['file_count'] += 1
                if last_active_days <= 90:
                    fs['recent_count'] += 1
                if len(fs['sample_files']) < 3:
                    fs['sample_files'].append(name)

            item = {
                'id': fid,
                'name': name,
                'mime_type': mime,
                'ext': ext,
                'parent_id': parent_id,
                'parent_name': sanitize_string(folder_by_id.get(parent_id, {}).get('name')) if parent_id else 'My Drive',
                'path': path,
                'in_root': in_root,
                'age_days': age_days,
                'last_active_days': last_active_days,
            }
            if in_root:
                unorganized_files.append(item)

        # Normalize folder stats
        existing_folders = []
        for fs in folder_stats.values():
            total = max(1, fs['file_count'])
            existing_folders.append({
                'id': fs['id'],
                'name': fs['name'],
                'path': fs['path'],
                'file_count': fs['file_count'],
                'recent_ratio': fs['recent_count'] / total,
                'sample_files': fs['sample_files'],
            })

        payload = {
            'existing_folders': existing_folders,
            'unorganized_files': unorganized_files,
        }

        try:
            return json.dumps(payload, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to serialize payload to JSON: {e}")
            # Fallback: create a minimal safe payload
            safe_payload = {
                'existing_folders': [],
                'unorganized_files': []
            }
            return json.dumps(safe_payload, indent=2, ensure_ascii=False)
    
    def _create_analysis_prompt(self, file_data: str) -> str:
        """Create the LLM prompt for drive analysis with reuse/merge constraints and coverage target."""
        return f"""
You are an expert Google Drive organizer.

INPUT JSON (two sections):
{file_data}

Definitions:
- existing_folders: array of folders with id, name, path, file_count, recent_ratio, sample_files
- unorganized_files: array of files currently in My Drive root with fields: id, name, mime_type, ext, parent_id, parent_name, path, in_root, age_days, last_active_days

Goals (strict):
1) Reuse existing folders whenever appropriate by returning target_folder_id that matches an existing folder id.
2) Merge near-duplicate folders (e.g., Academic vs Academics vs Academic Materials) into one canonical target; emit a merges plan.
3) Coverage: assign at least 80% of unorganized_files to a destination.
4) Do not create a new folder unless it will contain at least 3 files; avoid single-file folders.
5) Keep folder depth at most 2 levels and prefer simple, descriptive names.

Return a JSON object with this exact structure:
{{
  "proposed_folders": [
    {{ "name": "Folder Name", "description": "what goes here" }}
  ],
  "file_moves": [
    {{
      "file_id": "id-from-unorganized_files",
      "target_folder_id": "existing folder id if reusing",
      "proposed_folder": "name from proposed_folders if creating new (omit if using target_folder_id)",
      "file_name": "original name (echo for UI)",
      "current_parent": "echo current parent id if available"
    }}
  ],
  "merges": [
    {{ "from_folder_ids": ["id1","id2"], "to_folder_id": "canonicalId" }}
  ]
}}

Constraints:
- Prefer target_folder_id whenever a reasonable match exists; only use proposed_folder when necessary.
- Try to minimize the number of new folders and avoid scattering single files into many small folders.
"""
    
    async def generate_proposal(self, scan_id: str, files: List[Dict], folders: List[Dict]) -> Dict:
        """Generate AI proposal for drive organization"""
        try:
            logger.info(f"Starting AI analysis for scan {scan_id}")
            logger.info(f"Processing {len(files)} files and {len(folders)} folders")
            
            # Prepare data for LLM
            file_data = self._prepare_file_data(files, folders)
            logger.info(f"Prepared file data length: {len(file_data)}")
            
            # Validate JSON structure before sending to OpenAI
            try:
                json.loads(file_data)
                logger.info("JSON validation passed")
            except json.JSONDecodeError as e:
                logger.error(f"JSON validation failed: {e}")
                raise Exception(f"Invalid JSON structure: {e}")
            
            prompt = self._create_analysis_prompt(file_data)
            
            # Call OpenAI
            logger.info(f"Calling OpenAI for scan {scan_id}")
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an expert file organizer. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                max_tokens=10000,
                temperature=0.3
            )
            
            # Parse response
            try:
                result = json.loads(response.choices[0].message.content)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse OpenAI response as JSON: {e}")
                logger.error(f"Response content: {response.choices[0].message.content[:500]}...")
                raise Exception(f"OpenAI returned invalid JSON: {e}")
            
            # Create proposal
            proposal = {
                "scan_id": scan_id,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "total_items": len(files) + len(folders),
                "proposed_folders": result.get("proposed_folders", []),
                "file_moves": result.get("file_moves", []),
                "merges": result.get("merges", [])
            }
            
            logger.info(f"AI analysis completed for scan {scan_id}: {len(proposal['proposed_folders'])} folders, {len(proposal['file_moves'])} moves")
            return proposal
            
        except Exception as e:
            logger.error(f"AI analysis failed for scan {scan_id}: {str(e)}")
            raise Exception(f"AI analysis failed: {str(e)}") 