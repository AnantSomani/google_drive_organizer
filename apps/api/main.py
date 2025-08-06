"""Main FastAPI application for Drive Organizer."""

import os
import uuid
from typing import Dict, List, Optional, Tuple
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import structlog
from supabase import create_client
import openai
from dotenv import load_dotenv

# Load environment variables from root directory
load_dotenv("../../.env")

from drive_client import build_service, list_files, move_item, create_folder, DriveClientError
from classification import propose_structure, summarize_large_file_list

# Configure logging
import logging
import sys

# Set up file logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('api.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

def validate_scan_data(files: List[Dict], folders: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """Validate and sanitize scan data before AI processing"""
    validated_files = []
    validated_folders = []
    
    for file in files:
        if isinstance(file, dict) and 'id' in file and 'name' in file:
            # Sanitize file data
            sanitized_file = {
                'id': str(file.get('id', '')),
                'name': str(file.get('name', '')).replace('"', "'").replace('\n', ' ').replace('\r', ' '),
                'mimeType': str(file.get('mimeType', '')),
                'parents': file.get('parents', [])
            }
            validated_files.append(sanitized_file)
    
    for folder in folders:
        if isinstance(folder, dict) and 'id' in folder and 'name' in folder:
            # Sanitize folder data
            sanitized_folder = {
                'id': str(folder.get('id', '')),
                'name': str(folder.get('name', '')).replace('"', "'").replace('\n', ' ').replace('\r', ' '),
                'parents': folder.get('parents', [])
            }
            validated_folders.append(sanitized_folder)
    
    return validated_files, validated_folders

# Initialize FastAPI app
app = FastAPI(
    title="Drive Organizer API",
    description="AI-powered Google Drive file organization",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://localhost:3000",
        "https://*.vercel.app",
        "https://*.railway.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_ANON_KEY")

# Debug environment variables
logger.info(f"SUPABASE_URL from env: {repr(supabase_url)}")
logger.info(f"SUPABASE_ANON_KEY from env: {repr(supabase_key[:20]) if supabase_key else 'None'}...")

# Fallback to hardcoded values if environment variables are not loaded
if not supabase_url or not supabase_key:
    logger.warning("Environment variables not loaded, using hardcoded values")
    # exposed secrets
    supabase_url = "https://iulqasfnthyhaikxmlex.supabase.co"
    # exposed secrets
    supabase_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Iml1bHFhc2ZudGh5aGFpa3htbGV4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTQwMDExNTksImV4cCI6MjA2OTU3NzE1OX0.CzY05M-tyfX6uiBAM7MVZ0b00380RFGiavCUdIQanl8"

logger.info(f"Final SUPABASE_URL: {repr(supabase_url)}")
logger.info(f"Final SUPABASE_ANON_KEY: {repr(supabase_key[:20])}...")

# Initialize Supabase client with error handling
try:
    supabase = create_client(supabase_url, supabase_key)
    logger.info("✅ Supabase client initialized successfully")
except Exception as e:
    logger.error(f"❌ Failed to initialize Supabase client: {e}")
    import traceback
    logger.error(f"Traceback: {traceback.format_exc()}")
    supabase = None

# Configure OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Security
security = HTTPBearer()

# Pydantic models
class IngestRequest(BaseModel):
    """Request model for metadata ingestion."""
    pass

class IngestResponse(BaseModel):
    """Response model for metadata ingestion."""
    task_id: str
    status: str
    message: str

class ProposeRequest(BaseModel):
    """Request model for structure proposal."""
    snapshot_id: str

class ProposeResponse(BaseModel):
    """Response model for structure proposal."""
    proposal_id: str
    proposal: Dict
    status: str

class ApplyRequest(BaseModel):
    """Request model for applying structure."""
    proposal_id: str

class ApplyResponse(BaseModel):
    """Response model for applying structure."""
    success: bool
    message: str
    undo_log_id: str

class UndoRequest(BaseModel):
    """Request model for undo operation."""
    log_id: str

class UndoResponse(BaseModel):
    """Response model for undo operation."""
    success: bool
    message: str

class PreferencesRequest(BaseModel):
    """Request model for user preferences."""
    ignore_mime: List[str] = []
    ignore_large: bool = False
    max_file_size_mb: int = 100

class PreferencesResponse(BaseModel):
    """Response model for user preferences."""
    preferences: Dict

# Google Drive API models
class DriveFile(BaseModel):
    """Model for Google Drive file."""
    id: str
    name: str
    mime_type: str = ""
    size: int = 0
    created_time: str = ""
    modified_time: str = ""
    parents: List[str] = []
    web_view_link: str = ""

class DriveFolder(BaseModel):
    """Model for Google Drive folder."""
    id: str
    name: str
    created_time: str = ""
    modified_time: str = ""
    parents: List[str] = []
    web_view_link: str = ""

class DriveScanRequest(BaseModel):
    """Request model for Drive scan."""
    include_folders: bool = True
    include_files: bool = True
    max_results: int = 1000

class DriveScanResponse(BaseModel):
    """Response model for Drive scan."""
    scan_id: str
    status: str
    message: str
    file_count: int = 0
    folder_count: int = 0

class DriveFilesResponse(BaseModel):
    """Response model for Drive files list."""
    files: List[DriveFile]
    next_page_token: str = None
    total_count: int

class DriveFoldersResponse(BaseModel):
    """Response model for Drive folders list."""
    folders: List[DriveFolder]
    next_page_token: str = None
    total_count: int

class DriveScanStatusResponse(BaseModel):
    """Response model for Drive scan status."""
    scan_id: str
    status: str
    file_count: int
    folder_count: int
    processed_count: int
    error_message: Optional[str] = None
    completed_at: Optional[str] = None

class TreeNode(BaseModel):
    """Model for tree node structure."""
    id: str
    name: str
    type: str  # 'file' or 'folder'
    mime_type: str = None
    size: int = None
    created_time: str = None
    modified_time: str = None
    parents: List[str] = []
    web_view_link: str = ""
    children: List['TreeNode'] = []
    level: int = 0

class ScanResultsResponse(BaseModel):
    """Response model for scan results with tree structure."""
    scan_id: str
    status: str
    file_count: int
    folder_count: int
    scan_timestamp: str
    tree_data: TreeNode
    files: List[DriveFile] = []
    folders: List[DriveFolder] = []


class AIProposal(BaseModel):
    """AI-generated organization proposal"""
    scan_id: str
    generated_at: str
    total_items: int
    proposed_folders: List[Dict]
    file_moves: List[Dict]

class AIAnalysisRequest(BaseModel):
    """Request model for AI analysis"""
    scan_id: str

class AIAnalysisResponse(BaseModel):
    """Response model for AI analysis"""
    analysis_id: str
    status: str
    message: str

class AIAnalysisStatusResponse(BaseModel):
    """Response model for AI analysis status"""
    analysis_id: str
    status: str
    progress: int = 0
    error_message: Optional[str] = None
    completed_at: Optional[str] = None

# Dependency to get current user
async def get_google_oauth_tokens(user_id: str) -> Dict:
    """Get Google OAuth tokens from database with automatic refresh."""
    try:
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        
        if not client_id or not client_secret:
            logger.error("Google OAuth credentials not configured in environment")
            raise Exception("Google OAuth credentials not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.")
        
        # Get tokens from database
        response = supabase.table("google_tokens").select("*").eq("user_id", user_id).execute()
        
        if not response.data:
            logger.warning("No Google tokens found for user", user_id=user_id)
            raise Exception("Google Drive not connected. Please sign in with Google OAuth first.")
        
        token_data = response.data[0]
        access_token = token_data["access_token"]
        refresh_token = token_data["refresh_token"]
        expires_at = token_data["expires_at"]
        
        # Check if token needs refresh (expires in next 2 minutes)
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        expires_at_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        
        if now > expires_at_dt - timedelta(minutes=2):
            logger.info("Refreshing Google OAuth token", user_id=user_id)
            new_tokens = await refresh_google_token(refresh_token)
            
            # Update database with new tokens
            supabase.table("google_tokens").update({
                "access_token": new_tokens["access_token"],
                "expires_at": new_tokens["expires_at"],
                "updated_at": "now()"
            }).eq("user_id", user_id).execute()
            
            access_token = new_tokens["access_token"]
        
        logger.info("Successfully retrieved Google OAuth tokens", user_id=user_id)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
            "token_uri": "https://oauth2.googleapis.com/token"
        }
        
    except Exception as e:
        logger.error("Failed to get Google OAuth tokens", error=str(e))
        raise Exception(f"Failed to get Google OAuth tokens: {str(e)}")

async def refresh_google_token(refresh_token: str) -> Dict:
    """Refresh Google OAuth token."""
    import httpx
    import time
    from datetime import datetime
    
    payload = {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post("https://oauth2.googleapis.com/token", data=payload)
        response.raise_for_status()
        data = response.json()
        
        return {
            "access_token": data["access_token"],
            "expires_at": datetime.fromtimestamp(time.time() + data["expires_in"]).isoformat() + "Z"
        }

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    """Get current user from JWT token."""
    if supabase is None:
        raise HTTPException(status_code=503, detail="Authentication service unavailable")
    
    try:
        # Verify the JWT token with Supabase
        user = supabase.auth.get_user(credentials.credentials)
        # Convert User object to dictionary
        return {
            "id": user.user.id,
            "email": user.user.email,
            "created_at": user.user.created_at,
            "updated_at": user.user.updated_at
        }
    except Exception as e:
        logger.error("Failed to authenticate user", error=str(e))
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "drive-organizer-api"}

# Google OAuth token storage endpoint
class TokenBody(BaseModel):
    access_token: str
    refresh_token: str
    expires_at: int
    scope: str = "drive"

@app.post("/api/google/store-token")
async def store_google_token(
    body: TokenBody,
    current_user: Dict = Depends(get_current_user)
):
    """Store Google OAuth tokens in database."""
    try:
        logger.info("Received token storage request", user_id=current_user["id"])
        
        # Convert expires_at from timestamp to ISO format
        from datetime import datetime
        expires_at = datetime.fromtimestamp(body.expires_at / 1000).isoformat() + "Z"
        
        logger.info("Token data", 
                   user_id=current_user["id"],
                   has_access_token=bool(body.access_token),
                   has_refresh_token=bool(body.refresh_token),
                   expires_at=expires_at)
        
        # Upsert tokens into database
        supabase.table("google_tokens").upsert({
            "user_id": current_user["id"],
            "access_token": body.access_token,
            "refresh_token": body.refresh_token,
            "expires_at": expires_at,
            "scope": body.scope
        }).execute()
        
        logger.info("Stored Google OAuth tokens", user_id=current_user["id"])
        
        return {"success": True, "message": "Tokens stored successfully"}
        
    except Exception as e:
        logger.error("Failed to store Google tokens", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to store tokens: {str(e)}")

# Metadata ingestion endpoint
@app.post("/ingest", response_model=IngestResponse)
async def ingest_metadata(
    request: IngestRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict = Depends(get_current_user)
):
    """Start metadata ingestion from Google Drive."""
    try:
        # Create ingestion status record
        ingestion_id = str(uuid.uuid4())
        supabase.table("ingestion_status").insert({
            "id": ingestion_id,
            "user_id": current_user["id"],
            "status": "pending"
        }).execute()
        
        # Start background task
        background_tasks.add_task(
            _ingest_metadata_task,
            current_user["id"],
            ingestion_id
        )
        
        logger.info("Started metadata ingestion", user_id=current_user["id"], task_id=ingestion_id)
        
        return IngestResponse(
            task_id=ingestion_id,
            status="pending",
            message="Metadata ingestion started"
        )
        
    except Exception as e:
        logger.error("Failed to start ingestion", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to start ingestion: {str(e)}")

async def _ingest_metadata_task(user_id: str, task_id: str):
    """Background task for metadata ingestion."""
    try:
        # Update status to processing
        supabase.table("ingestion_status").update({
            "status": "processing"
        }).eq("id", task_id).execute()
        
        # Get user's Google credentials from Supabase
        # Note: In a real implementation, you'd store and retrieve OAuth tokens
        # For now, we'll use environment variables for demo purposes
        user_credentials = {
            "access_token": os.getenv("GOOGLE_ACCESS_TOKEN"),
            "refresh_token": os.getenv("GOOGLE_REFRESH_TOKEN"),
            "client_id": os.getenv("GOOGLE_CLIENT_ID"),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET")
        }
        
        # Build Drive service
        service = build_service(user_credentials)
        
        # List all files
        files = list_files(service)
        
        # Generate snapshot ID
        snapshot_id = str(uuid.uuid4())
        
        # Store metadata in chunks
        chunk_size = 100
        for i in range(0, len(files), chunk_size):
            chunk = files[i:i + chunk_size]
            supabase.table("metadata_raw").insert({
                "user_id": user_id,
                "snapshot_id": snapshot_id,
                "file_metadata": chunk
            }).execute()
        
        # Update status to done
        supabase.table("ingestion_status").update({
            "status": "done",
            "total_files": len(files),
            "processed_files": len(files),
            "completed_at": "now()"
        }).eq("id", task_id).execute()
        
        logger.info("Completed metadata ingestion", 
                   user_id=user_id, 
                   task_id=task_id, 
                   file_count=len(files))
        
    except Exception as e:
        logger.error("Failed to ingest metadata", error=str(e), task_id=task_id)
        
        # Update status to error
        supabase.table("ingestion_status").update({
            "status": "error",
            "error_message": str(e)
        }).eq("id", task_id).execute()

# Structure proposal endpoint
@app.post("/propose", response_model=ProposeResponse)
async def propose_structure_endpoint(
    request: ProposeRequest,
    current_user: Dict = Depends(get_current_user)
):
    """Generate AI-powered folder structure proposal."""
    try:
        # Get metadata for the snapshot
        metadata_response = supabase.table("metadata_raw").select("*").eq(
            "user_id", current_user["id"]
        ).eq("snapshot_id", request.snapshot_id).execute()
        
        if not metadata_response.data:
            raise HTTPException(status_code=404, detail="No metadata found for snapshot")
        
        # Extract file metadata
        all_metadata = []
        for record in metadata_response.data:
            all_metadata.extend(record["file_metadata"])
        
        # Get user preferences
        preferences_response = supabase.table("preferences").select("*").eq(
            "user_id", current_user["id"]
        ).execute()
        
        user_preferences = preferences_response.data[0] if preferences_response.data else {}
        
        # Summarize if too many files
        if len(all_metadata) > 4000:
            all_metadata = summarize_large_file_list(all_metadata)
        
        # Generate proposal
        proposal = propose_structure(all_metadata, user_preferences)
        
        # Store proposal
        proposal_id = str(uuid.uuid4())
        supabase.table("session_proposals").insert({
            "id": proposal_id,
            "user_id": current_user["id"],
            "snapshot_id": request.snapshot_id,
            "proposal": proposal,
            "status": "draft"
        }).execute()
        
        logger.info("Generated structure proposal", 
                   user_id=current_user["id"], 
                   proposal_id=proposal_id)
        
        return ProposeResponse(
            proposal_id=proposal_id,
            proposal=proposal,
            status="draft"
        )
        
    except Exception as e:
        logger.error("Failed to generate proposal", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to generate proposal: {str(e)}")

# Apply structure endpoint
@app.post("/apply", response_model=ApplyResponse)
async def apply_structure(
    request: ApplyRequest,
    current_user: Dict = Depends(get_current_user)
):
    """Apply the proposed folder structure to Google Drive."""
    try:
        # Get the proposal
        proposal_response = supabase.table("session_proposals").select("*").eq(
            "id", request.proposal_id
        ).eq("user_id", current_user["id"]).execute()
        
        if not proposal_response.data:
            raise HTTPException(status_code=404, detail="Proposal not found")
        
        proposal_data = proposal_response.data[0]
        proposal = proposal_data["proposal"]
        
        # Get user's Google credentials
        user_credentials = {
            "access_token": os.getenv("GOOGLE_ACCESS_TOKEN"),
            "refresh_token": os.getenv("GOOGLE_REFRESH_TOKEN"),
            "client_id": os.getenv("GOOGLE_CLIENT_ID"),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET")
        }
        
        # Build Drive service
        service = build_service(user_credentials)
        
        # Track changes for undo
        changes = []
        
        # Apply the structure
        for folder in proposal.get("root_folders", []):
            await _apply_folder_structure(service, folder, changes)
        
        # Create undo log
        undo_log_id = str(uuid.uuid4())
        supabase.table("undo_logs").insert({
            "id": undo_log_id,
            "user_id": current_user["id"],
            "session_proposal_id": request.proposal_id,
            "changes": changes
        }).execute()
        
        # Update proposal status
        supabase.table("session_proposals").update({
            "status": "applied"
        }).eq("id", request.proposal_id).execute()
        
        logger.info("Applied folder structure", 
                   user_id=current_user["id"], 
                   proposal_id=request.proposal_id,
                   changes_count=len(changes))
        
        return ApplyResponse(
            success=True,
            message=f"Successfully applied structure with {len(changes)} changes",
            undo_log_id=undo_log_id
        )
        
    except Exception as e:
        logger.error("Failed to apply structure", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to apply structure: {str(e)}")

async def _apply_folder_structure(service, folder: Dict, changes: List):
    """Recursively apply folder structure."""
    # Create folder if it doesn't exist
    folder_id = await _ensure_folder_exists(service, folder["name"])
    
    # Move files to this folder
    for file_id in folder.get("files", []):
        try:
            move_item(service, file_id, folder_id)
            changes.append({
                "type": "move",
                "file_id": file_id,
                "new_parent_id": folder_id,
                "folder_name": folder["name"]
            })
        except DriveClientError as e:
            logger.warning(f"Failed to move file {file_id}: {str(e)}")
    
    # Process children
    for child in folder.get("children", []):
        await _apply_folder_structure(service, child, changes)

async def _ensure_folder_exists(service, folder_name: str) -> str:
    """Ensure a folder exists and return its ID."""
    # For demo purposes, we'll create a new folder
    # In a real implementation, you'd check if it exists first
    folder = create_folder(service, folder_name)
    return folder["id"]

# Undo endpoint
@app.post("/undo/{log_id}", response_model=UndoResponse)
async def undo_changes(
    log_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """Undo the changes made by a previous apply operation."""
    try:
        # Get the undo log
        log_response = supabase.table("undo_logs").select("*").eq(
            "id", log_id
        ).eq("user_id", current_user["id"]).execute()
        
        if not log_response.data:
            raise HTTPException(status_code=404, detail="Undo log not found")
        
        log_data = log_response.data[0]
        
        if log_data["reverted"]:
            raise HTTPException(status_code=400, detail="Changes already reverted")
        
        # Get user's Google credentials
        user_credentials = {
            "access_token": os.getenv("GOOGLE_ACCESS_TOKEN"),
            "refresh_token": os.getenv("GOOGLE_REFRESH_TOKEN"),
            "client_id": os.getenv("GOOGLE_CLIENT_ID"),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET")
        }
        
        # Build Drive service
        service = build_service(user_credentials)
        
        # Reverse the changes
        changes = log_data["changes"]
        for change in reversed(changes):
            if change["type"] == "move":
                try:
                    # Move file back to root (or original location)
                    move_item(service, change["file_id"], "root")
                except DriveClientError as e:
                    logger.warning(f"Failed to undo move for file {change['file_id']}: {str(e)}")
        
        # Mark as reverted
        supabase.table("undo_logs").update({
            "reverted": True,
            "reverted_at": "now()"
        }).eq("id", log_id).execute()
        
        # Update proposal status
        if log_data["session_proposal_id"]:
            supabase.table("session_proposals").update({
                "status": "reverted"
            }).eq("id", log_data["session_proposal_id"]).execute()
        
        logger.info("Reverted changes", user_id=current_user["id"], log_id=log_id)
        
        return UndoResponse(
            success=True,
            message=f"Successfully reverted {len(changes)} changes"
        )
        
    except Exception as e:
        logger.error("Failed to undo changes", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to undo changes: {str(e)}")

# Preferences endpoints
@app.get("/preferences", response_model=PreferencesResponse)
async def get_preferences(current_user: Dict = Depends(get_current_user)):
    """Get user preferences."""
    try:
        response = supabase.table("preferences").select("*").eq(
            "user_id", current_user["id"]
        ).execute()
        
        if response.data:
            return PreferencesResponse(preferences=response.data[0])
        else:
            # Return default preferences
            return PreferencesResponse(preferences={
                "ignore_mime": [],
                "ignore_large": False,
                "max_file_size_mb": 100
            })
            
    except Exception as e:
        logger.error("Failed to get preferences", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get preferences: {str(e)}")

@app.put("/preferences", response_model=PreferencesResponse)
async def update_preferences(
    request: PreferencesRequest,
    current_user: Dict = Depends(get_current_user)
):
    """Update user preferences."""
    try:
        preferences_data = {
            "user_id": current_user["id"],
            "ignore_mime": request.ignore_mime,
            "ignore_large": request.ignore_large,
            "max_file_size_mb": request.max_file_size_mb
        }
        
        # Upsert preferences
        supabase.table("preferences").upsert(preferences_data).execute()
        
        logger.info("Updated preferences", user_id=current_user["id"])
        
        return PreferencesResponse(preferences=preferences_data)
        
    except Exception as e:
        logger.error("Failed to update preferences", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to update preferences: {str(e)}")

# Status endpoints
@app.get("/ingest/status/{task_id}")
async def get_ingest_status(task_id: str, current_user: Dict = Depends(get_current_user)):
    """Get the status of a metadata ingestion task."""
    try:
        response = supabase.table("ingestion_status").select("*").eq(
            "id", task_id
        ).eq("user_id", current_user["id"]).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return response.data[0]
        
    except Exception as e:
        logger.error("Failed to get ingest status", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")

@app.get("/proposals")
async def get_proposals(current_user: Dict = Depends(get_current_user)):
    """Get all proposals for the current user."""
    try:
        response = supabase.table("session_proposals").select("*").eq(
            "user_id", current_user["id"]
        ).order("created_at", desc=True).execute()
        
        return {"proposals": response.data}
        
    except Exception as e:
        logger.error("Failed to get proposals", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get proposals: {str(e)}")

# Google Drive API endpoints
@app.get("/api/drive/files", response_model=DriveFilesResponse)
async def get_drive_files(
    page_token: str = None,
    page_size: int = 50,
    current_user: Dict = Depends(get_current_user)
):
    """List user's Google Drive files with pagination."""
    try:
        # Get user's Google OAuth tokens from database
        try:
            user_credentials = await get_google_oauth_tokens(current_user["id"])
        except Exception as e:
            logger.warning("Failed to get Google OAuth tokens", error=str(e))
            raise HTTPException(
                status_code=400, 
                detail="Please sign in with Google to access Drive files. Error: " + str(e)
            )
        
        # Build Drive service
        service = build_service(user_credentials)
        
        # List files with pagination
        files_result = list_files(service, page_token=page_token, page_size=page_size)
        
        # Convert to Pydantic models
        drive_files = []
        files_list = files_result.get("files", [])
        for file in files_list:
            drive_files.append(DriveFile(
                id=file.get("id", ""),
                name=file.get("name", ""),
                mime_type=file.get("mimeType", ""),
                size=int(file.get("size", 0)),
                created_time=file.get("createdTime", ""),
                modified_time=file.get("modifiedTime", ""),
                parents=file.get("parents", []),
                web_view_link=file.get("webViewLink", "")
            ))
        
        logger.info("Retrieved Drive files", 
                   user_id=current_user["id"], 
                   file_count=len(drive_files))
        
        return DriveFilesResponse(
            files=drive_files,
            next_page_token=files_result.get("nextPageToken"),
            total_count=len(drive_files)
        )
        
    except DriveClientError as e:
        logger.error("Drive API error", error=str(e))
        raise HTTPException(status_code=400, detail=f"Drive API error: {str(e)}")
    except Exception as e:
        logger.error("Failed to get Drive files", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get Drive files: {str(e)}")

@app.get("/api/drive/folders", response_model=DriveFoldersResponse)
async def get_drive_folders(
    page_token: str = None,
    page_size: int = 50,
    current_user: Dict = Depends(get_current_user)
):
    """List user's Google Drive folders with pagination."""
    try:
        # Get user's Google OAuth tokens from database
        try:
            user_credentials = await get_google_oauth_tokens(current_user["id"])
        except Exception as e:
            logger.warning("Failed to get Google OAuth tokens", error=str(e))
            raise HTTPException(
                status_code=400, 
                detail="Please sign in with Google to access Drive folders. Error: " + str(e)
            )
        
        # Build Drive service
        service = build_service(user_credentials)
        
        # List folders (folders are files with mimeType = 'application/vnd.google-apps.folder')
        folders_result = list_files(service, 
                                  page_token=page_token, 
                                  page_size=page_size,
                                  mime_type="application/vnd.google-apps.folder")
        
        # Convert to Pydantic models
        drive_folders = []
        folders_list = folders_result.get("files", [])
        for folder in folders_list:
            drive_folders.append(DriveFolder(
                id=folder.get("id", ""),
                name=folder.get("name", ""),
                created_time=folder.get("createdTime", ""),
                modified_time=folder.get("modifiedTime", ""),
                parents=folder.get("parents", []),
                web_view_link=folder.get("webViewLink", "")
            ))
        
        logger.info("Retrieved Drive folders", 
                   user_id=current_user["id"], 
                   folder_count=len(drive_folders))
        
        return DriveFoldersResponse(
            folders=drive_folders,
            next_page_token=folders_result.get("nextPageToken"),
            total_count=len(drive_folders)
        )
        
    except DriveClientError as e:
        logger.error("Drive API error", error=str(e))
        raise HTTPException(status_code=400, detail=f"Drive API error: {str(e)}")
    except Exception as e:
        logger.error("Failed to get Drive folders", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get Drive folders: {str(e)}")

@app.post("/api/drive/scan", response_model=DriveScanResponse)
async def scan_drive(
    request: DriveScanRequest,
    background_tasks: BackgroundTasks,
    access_token: str = None,
    current_user: Dict = Depends(get_current_user)
):
    """Initiate a comprehensive scan of the user's Google Drive."""
    try:
        # Create scan record
        # Generate scan ID
        scan_id = str(uuid.uuid4())
        supabase.table("drive_scans").insert({
            "id": scan_id,
            "user_id": current_user["id"],
            "status": "pending",
            "include_folders": request.include_folders,
            "include_files": request.include_files,
            "max_results": request.max_results
        }).execute()
        
        # Start background scan task
        background_tasks.add_task(
            _scan_drive_task,
            current_user["id"],
            scan_id,
            request.include_folders,
            request.include_files,
            request.max_results
        )
        
        logger.info("Started Drive scan", 
                   user_id=current_user["id"], 
                   scan_id=scan_id)
        
        return DriveScanResponse(
            scan_id=scan_id,
            status="pending",
            message="Drive scan started",
            file_count=0,
            folder_count=0
        )
        
    except Exception as e:
        logger.error("Failed to start Drive scan", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to start scan: {str(e)}")

async def _scan_drive_task(
    user_id: str, 
    scan_id: str, 
    include_folders: bool, 
    include_files: bool, 
    max_results: int
):
    """Background task for comprehensive Drive scanning."""
    try:
        # Update status to processing
        supabase.table("drive_scans").update({
            "status": "processing"
        }).eq("id", scan_id).execute()
        
        # Get user's Google OAuth tokens from their Supabase session
        try:
            user_credentials = await get_google_oauth_tokens(user_id)
        except Exception as e:
            logger.warning("Failed to get Google OAuth tokens", error=str(e))
            raise Exception(f"Please sign in with Google to access Drive. Error: {str(e)}")
        
        # Build Drive service
        service = build_service(user_credentials)
        
        all_files = []
        all_folders = []
        
        # Recursively scan all items (files and folders)
        if include_files or include_folders:
            all_items = await _recursive_scan_drive(service, max_results=max_results)
            
            # Separate files and folders
            for item in all_items:
                if item.get("mimeType") == "application/vnd.google-apps.folder":
                    if include_folders:
                        all_folders.append(item)
                else:
                    if include_files:
                        all_files.append(item)
        
        file_count = len(all_files)
        folder_count = len(all_folders)
        
        # Store file metadata with cleanup of existing data
        if all_files:
            # Delete existing files for this scan_id (if any)
            supabase.table("drive_files").delete().eq("scan_id", scan_id).execute()
            # Insert new files
            supabase.table("drive_files").insert({
                "scan_id": scan_id,
                "user_id": user_id,
                "files": all_files
            }).execute()
        
        # Store folder metadata with cleanup of existing data
        if all_folders:
            # Delete existing folders for this scan_id (if any)
            supabase.table("drive_folders").delete().eq("scan_id", scan_id).execute()
            # Insert new folders
            supabase.table("drive_folders").insert({
                "scan_id": scan_id,
                "user_id": user_id,
                "folders": all_folders
            }).execute()
        
        # Update scan status
        supabase.table("drive_scans").update({
            "status": "completed",
            "file_count": file_count,
            "folder_count": folder_count,
            "completed_at": "now()"
        }).eq("id", scan_id).execute()
        
        # Clean up old scans
        await cleanup_old_scans(user_id, keep_count=5)
        
        logger.info("Completed Drive scan", 
                   user_id=user_id, 
                   scan_id=scan_id,
                   file_count=file_count,
                   folder_count=folder_count)
        
    except Exception as e:
        logger.error("Failed to scan Drive", error=str(e), scan_id=scan_id)
        
        # Update status to error
        supabase.table("drive_scans").update({
            "status": "error",
            "error_message": str(e)
        }).eq("id", scan_id).execute()

async def _recursive_scan_drive(service, max_results: int = 1000, parent_id: str = None) -> List[Dict]:
    """Recursively scan Google Drive to get all files and folders."""
    all_items = []
    
    try:
        # Build query for items in the current folder (or root if parent_id is None)
        query = "trashed=false"
        if parent_id:
            query += f" and '{parent_id}' in parents"
        else:
            query += " and 'root' in parents"
        
        # Get items in current folder
        results = service.files().list(
            q=query,
            pageSize=1000,
            fields="nextPageToken, files(id, name, mimeType, parents, createdTime, modifiedTime, size, webViewLink)"
        ).execute()
        
        items = results.get('files', [])
        
        for item in items:
            all_items.append(item)
            
            # If this is a folder, recursively scan its contents
            if item.get("mimeType") == "application/vnd.google-apps.folder":
                logger.info(f"Scanning folder: {item.get('name', 'Unknown')} (ID: {item.get('id')})")
                sub_items = await _recursive_scan_drive(service, max_results, item.get('id'))
                all_items.extend(sub_items)
            
            # Check if we've reached the max results limit
            if max_results and len(all_items) >= max_results:
                all_items = all_items[:max_results]
                break
        
        # Handle pagination
        while 'nextPageToken' in results and (not max_results or len(all_items) < max_results):
            results = service.files().list(
                q=query,
                pageSize=1000,
                pageToken=results['nextPageToken'],
                fields="nextPageToken, files(id, name, mimeType, parents, createdTime, modifiedTime, size, webViewLink)"
            ).execute()
            
            items = results.get('files', [])
            
            for item in items:
                all_items.append(item)
                
                # If this is a folder, recursively scan its contents
                if item.get("mimeType") == "application/vnd.google-apps.folder":
                    logger.info(f"Scanning folder: {item.get('name', 'Unknown')} (ID: {item.get('id')})")
                    sub_items = await _recursive_scan_drive(service, max_results, item.get('id'))
                    all_items.extend(sub_items)
                
                # Check if we've reached the max results limit
                if max_results and len(all_items) >= max_results:
                    all_items = all_items[:max_results]
                    break
            
            if max_results and len(all_items) >= max_results:
                break
        
        logger.info(f"Scanned {len(all_items)} items from folder {parent_id or 'root'}")
        return all_items
        
    except Exception as e:
        logger.error(f"Error scanning folder {parent_id or 'root'}", error=str(e))
        return all_items

@app.get("/api/drive/scan/status/{scan_id}", response_model=DriveScanStatusResponse)
async def get_drive_scan_status(
    scan_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """Get the status of a Drive scan."""
    try:
        response = supabase.table("drive_scans").select("*").eq(
            "id", scan_id
        ).eq("user_id", current_user["id"]).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        scan_data = response.data[0]
        
        return DriveScanStatusResponse(
            scan_id=scan_id,
            status=scan_data["status"],
            file_count=scan_data.get("file_count", 0),
            folder_count=scan_data.get("folder_count", 0),
            processed_count=scan_data.get("file_count", 0) + scan_data.get("folder_count", 0),
            error_message=scan_data.get("error_message"),
            completed_at=scan_data.get("completed_at")
        )
        
    except Exception as e:
        logger.error("Failed to get scan status", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get scan status: {str(e)}")

def build_tree_structure(files: List[Dict], folders: List[Dict]) -> TreeNode:
    """Build a tree structure from files and folders data."""
    try:
        # Create a map of all items by ID
        items_map = {}
        
        # Add folders to the map
        for folder in folders:
            try:
                items_map[folder["id"]] = {
                    "id": folder["id"],
                    "name": folder["name"],
                    "type": "folder",
                    "created_time": folder.get("createdTime", ""),
                    "modified_time": folder.get("modifiedTime", ""),
                    "parents": folder.get("parents", []),
                    "web_view_link": folder.get("webViewLink", ""),
                    "children": [],
                    "level": 0
                }
            except KeyError as e:
                logger.warning(f"Missing required field in folder: {e}", folder_id=folder.get("id"))
                continue
        
        # Add files to the map
        for file in files:
            try:
                items_map[file["id"]] = {
                    "id": file["id"],
                    "name": file["name"],
                    "type": "file",
                    "mime_type": file.get("mimeType", ""),
                    "size": file.get("size", 0),
                    "created_time": file.get("createdTime", ""),
                    "modified_time": file.get("modifiedTime", ""),
                    "parents": file.get("parents", []),
                    "web_view_link": file.get("webViewLink", ""),
                    "children": [],
                    "level": 0
                }
            except KeyError as e:
                logger.warning(f"Missing required field in file: {e}", file_id=file.get("id"))
                continue
        
        # Build the tree structure
        root_items = []
        
        for item_id, item in items_map.items():
            if not item["parents"] or "root" in item["parents"]:
                # This is a root item
                root_items.append(item)
            else:
                # This item has parents, add it to the appropriate parent
                for parent_id in item["parents"]:
                    if parent_id in items_map:
                        parent = items_map[parent_id]
                        parent["children"].append(item)
                        item["level"] = parent["level"] + 1
                    else:
                        # Parent not found, treat as root item
                        logger.warning(f"Parent {parent_id} not found for item {item_id}, treating as root")
                        root_items.append(item)
                        break
        
        # Create the root node
        root_node = TreeNode(
            id="root",
            name="My Drive",
            type="folder",
            children=root_items,
            level=0
        )
        
        return root_node
        
    except Exception as e:
        logger.error("Failed to build tree structure", error=str(e))
        # Return a minimal root node if tree building fails
        return TreeNode(
            id="root",
            name="My Drive",
            type="folder",
            children=[],
            level=0
        )

@app.get("/api/drive/scan-results/latest", response_model=ScanResultsResponse)
async def get_latest_scan_results(
    current_user: Dict = Depends(get_current_user)
):
    """Get the latest completed scan results for the current user."""
    try:
        # Get the latest completed scan
        scan_response = supabase.table("drive_scans").select("*").eq(
            "user_id", current_user["id"]
        ).eq("status", "completed").order("completed_at", desc=True).limit(1).execute()
        
        if not scan_response.data:
            raise HTTPException(
                status_code=404, 
                detail="No completed scans found. Please run a scan first."
            )
        
        scan_data = scan_response.data[0]
        scan_id = scan_data["id"]
        
        # Get files data
        files_response = supabase.table("drive_files").select("files").eq(
            "scan_id", scan_id
        ).eq("user_id", current_user["id"]).execute()
        
        files = []
        if files_response.data:
            files = files_response.data[0]["files"]
        
        # Get folders data
        folders_response = supabase.table("drive_folders").select("folders").eq(
            "scan_id", scan_id
        ).eq("user_id", current_user["id"]).execute()
        
        folders = []
        if folders_response.data:
            folders = folders_response.data[0]["folders"]
        
        # Build tree structure
        tree_data = build_tree_structure(files, folders)
        
        # Convert to Pydantic models for response
        drive_files = [DriveFile(**file) for file in files]
        drive_folders = [DriveFolder(**folder) for folder in folders]
        
        return ScanResultsResponse(
            scan_id=scan_id,
            status=scan_data["status"],
            file_count=scan_data.get("file_count", 0),
            folder_count=scan_data.get("folder_count", 0),
            scan_timestamp=scan_data.get("completed_at", scan_data.get("started_at")),
            tree_data=tree_data,
            files=drive_files,
            folders=drive_folders
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get latest scan results", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get latest scan results: {str(e)}")

@app.get("/api/drive/scan-results/{scan_id}", response_model=ScanResultsResponse)
async def get_scan_results(
    scan_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """Get the complete scan results with tree structure for a specific scan."""
    try:
        # Get scan metadata
        scan_response = supabase.table("drive_scans").select("*").eq(
            "id", scan_id
        ).eq("user_id", current_user["id"]).execute()
        
        if not scan_response.data:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        scan_data = scan_response.data[0]
        
        # Check if scan is completed
        if scan_data["status"] != "completed":
            raise HTTPException(
                status_code=400, 
                detail=f"Scan is not completed. Current status: {scan_data['status']}"
            )
        
        # Get files data
        files_response = supabase.table("drive_files").select("files").eq(
            "scan_id", scan_id
        ).eq("user_id", current_user["id"]).execute()
        
        files = []
        if files_response.data:
            files = files_response.data[0]["files"]
        
        # Get folders data
        folders_response = supabase.table("drive_folders").select("folders").eq(
            "scan_id", scan_id
        ).eq("user_id", current_user["id"]).execute()
        
        folders = []
        if folders_response.data:
            folders = folders_response.data[0]["folders"]
        
        # Build tree structure
        tree_data = build_tree_structure(files, folders)
        
        # Convert to Pydantic models for response
        drive_files = [DriveFile(**file) for file in files]
        drive_folders = [DriveFolder(**folder) for folder in folders]
        
        return ScanResultsResponse(
            scan_id=scan_id,
            status=scan_data["status"],
            file_count=scan_data.get("file_count", 0),
            folder_count=scan_data.get("folder_count", 0),
            scan_timestamp=scan_data.get("completed_at", scan_data.get("started_at")),
            tree_data=tree_data,
            files=drive_files,
            folders=drive_folders
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get scan results", error=str(e), scan_id=scan_id)
        raise HTTPException(status_code=500, detail=f"Failed to get scan results: {str(e)}")

# Initialize AI service
try:
    from ai_service import AIService
    ai_service = AIService()
    logger.info("✅ AI service initialized successfully")
except Exception as e:
    logger.error(f"❌ Failed to initialize AI service: {e}")
    ai_service = None

@app.post("/api/ai/analyze/{scan_id}", response_model=AIAnalysisResponse)
async def analyze_drive_with_ai(
    scan_id: str,
    background_tasks: BackgroundTasks,
    current_user: Dict = Depends(get_current_user)
):
    """Start AI analysis of drive structure"""
    try:
        logger.info(f"Starting AI analysis request for scan {scan_id}, user {current_user['id']}")
        
        if not ai_service:
            logger.error("AI service not available")
            raise HTTPException(status_code=500, detail="AI service not available")
        
        logger.info("AI service is available, proceeding with analysis")
        
        # Check if analysis already exists for this scan
        try:
            logger.info("Checking for existing analysis...")
            existing_response = supabase.table("ai_analyses").select("id, status").eq(
                "scan_id", scan_id
            ).eq("user_id", current_user["id"]).execute()
            logger.info(f"Existing analysis check completed: {len(existing_response.data) if existing_response.data else 0} found")
        except Exception as e:
            logger.error(f"Database error checking existing analysis: {e}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        
        if existing_response.data:
            existing_analysis = existing_response.data[0]
            analysis_id = existing_analysis["id"]
            
            # If analysis is already completed, return it
            if existing_analysis["status"] == "completed":
                return AIAnalysisResponse(
                    analysis_id=analysis_id,
                    status="completed",
                    message="Analysis already completed"
                )
            
            # If analysis is in progress, return it
            if existing_analysis["status"] == "processing":
                return AIAnalysisResponse(
                    analysis_id=analysis_id,
                    status="processing",
                    message="Analysis already in progress"
                )
            
            # If analysis failed, we can restart it
            # Update the existing record
            supabase.table("ai_analyses").update({
                "status": "processing",
                "progress": 0,
                "error_message": None,
                "completed_at": None
            }).eq("id", analysis_id).execute()
        else:
            # Generate new analysis ID
            analysis_id = str(uuid.uuid4())
            
            # Store analysis status
            supabase.table("ai_analyses").insert({
                "id": analysis_id,
                "scan_id": scan_id,
                "user_id": current_user["id"],
                "status": "processing",
                "created_at": "now()"
            }).execute()
        
        # Start background task
        try:
            logger.info(f"Starting background task for analysis {analysis_id}")
            background_tasks.add_task(
                _ai_analysis_task,
                analysis_id=analysis_id,
                scan_id=scan_id,
                user_id=current_user["id"]
            )
            logger.info("Background task started successfully")
        except Exception as e:
            logger.error(f"Failed to start background task: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to start background task: {str(e)}")
        
        return AIAnalysisResponse(
            analysis_id=analysis_id,
            status="processing",
            message="AI analysis started"
        )
        
    except Exception as e:
        logger.error("Failed to start AI analysis", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to start analysis: {str(e)}")

@app.get("/api/ai/analysis/{analysis_id}", response_model=AIAnalysisStatusResponse)
async def get_ai_analysis_status(
    analysis_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """Get AI analysis status"""
    try:
        response = supabase.table("ai_analyses").select("*").eq(
            "id", analysis_id
        ).eq("user_id", current_user["id"]).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Analysis not found")
        
        analysis_data = response.data[0]
        
        return AIAnalysisStatusResponse(
            analysis_id=analysis_id,
            status=analysis_data["status"],
            progress=analysis_data.get("progress", 0),
            error_message=analysis_data.get("error_message"),
            completed_at=analysis_data.get("completed_at")
        )
        
    except Exception as e:
        logger.error("Failed to get analysis status", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")

@app.get("/api/ai/proposal/{analysis_id}")
async def get_ai_proposal(
    analysis_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """Get AI-generated organization proposal"""
    try:
        # Get analysis data
        response = supabase.table("ai_analyses").select("*").eq(
            "id", analysis_id
        ).eq("user_id", current_user["id"]).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Analysis not found")
        
        analysis_data = response.data[0]
        
        if analysis_data["status"] != "completed":
            raise HTTPException(status_code=400, detail="Analysis not completed")
        
        # Get proposal data
        proposal_response = supabase.table("ai_proposals").select("*").eq(
            "analysis_id", analysis_id
        ).execute()
        
        if not proposal_response.data:
            raise HTTPException(status_code=404, detail="Proposal not found")
        
        return proposal_response.data[0]["proposal_data"]
        
    except Exception as e:
        logger.error("Failed to get AI proposal", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get proposal: {str(e)}")

@app.post("/api/ai/apply/{analysis_id}")
async def apply_ai_proposal(
    analysis_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """Apply AI proposal to Google Drive"""
    try:
        # Get proposal
        proposal_response = supabase.table("ai_proposals").select("*").eq(
            "analysis_id", analysis_id
        ).execute()
        
        if not proposal_response.data:
            raise HTTPException(status_code=404, detail="Proposal not found")
        
        proposal_data = proposal_response.data[0]["proposal_data"]
        
        # Get Google Drive service
        user_credentials = await get_google_oauth_tokens(current_user["id"])
        service = build_service(user_credentials)
        
        # Apply changes
        results = await _apply_ai_proposal(service, proposal_data)
        
        return {
            "success": True,
            "results": results,
            "message": f"Applied {len(results['successful_moves'])} moves successfully"
        }
        
    except Exception as e:
        logger.error("Failed to apply AI proposal", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

async def _ai_analysis_task(analysis_id: str, scan_id: str, user_id: str):
    """Background task for AI analysis"""
    try:
        logger.info(f"Starting AI analysis background task for {analysis_id}")
        
        # Update status to processing
        supabase.table("ai_analyses").update({
            "status": "processing",
            "progress": 10
        }).eq("id", analysis_id).execute()
        
        logger.info("Updated analysis status to processing")
        
        # Get scan data
        scan_response = supabase.table("drive_scans").select("*").eq(
            "id", scan_id
        ).eq("user_id", user_id).execute()
        
        if not scan_response.data:
            raise Exception("Scan not found")
        
        scan_data = scan_response.data[0]
        
        # Get files and folders
        try:
            logger.info(f"Retrieving files and folders for scan {scan_id}")
            files_response = supabase.table("drive_files").select("files").eq(
                "scan_id", scan_id
            ).execute()
            
            folders_response = supabase.table("drive_folders").select("folders").eq(
                "scan_id", scan_id
            ).execute()
            
            logger.info(f"Files response: {len(files_response.data) if files_response.data else 0} records")
            logger.info(f"Folders response: {len(folders_response.data) if folders_response.data else 0} records")
            
            files = files_response.data[0]["files"] if files_response.data else []
            folders = folders_response.data[0]["folders"] if folders_response.data else []
            
            logger.info(f"Retrieved {len(files)} files and {len(folders)} folders")
            
            # Validate and sanitize data before AI processing
            logger.info("Validating and sanitizing scan data")
            validated_files, validated_folders = validate_scan_data(files, folders)
            
            logger.info(f"After validation: {len(validated_files)} files and {len(validated_folders)} folders")
            
            # Log a sample of the validated data
            if validated_files:
                logger.info(f"Sample validated file: {validated_files[0] if len(validated_files) > 0 else 'No files'}")
            if validated_folders:
                logger.info(f"Sample validated folder: {validated_folders[0] if len(validated_folders) > 0 else 'No folders'}")
                
        except Exception as e:
            logger.error(f"Failed to retrieve files/folders: {e}")
            raise Exception(f"Failed to retrieve scan data: {str(e)}")
        
        # Update progress
        supabase.table("ai_analyses").update({
            "progress": 30
        }).eq("id", analysis_id).execute()
        
        # Generate AI proposal with validated data
        logger.info(f"Calling AI service with {len(validated_files)} validated files and {len(validated_folders)} validated folders")
        try:
            proposal = await ai_service.generate_proposal(scan_id, validated_files, validated_folders)
            logger.info("AI service call completed successfully")
        except Exception as e:
            logger.error(f"AI service call failed: {e}")
            raise e
        
        # Update progress
        supabase.table("ai_analyses").update({
            "progress": 80
        }).eq("id", analysis_id).execute()
        
        # Store proposal
        logger.info("Storing AI proposal in database")
        try:
            supabase.table("ai_proposals").insert({
                "analysis_id": analysis_id,
                "scan_id": scan_id,
                "user_id": user_id,
                "proposal_data": proposal,
                "created_at": "now()"
            }).execute()
            logger.info("AI proposal stored successfully")
        except Exception as e:
            logger.error(f"Failed to store AI proposal: {e}")
            raise e
        
        # Update status to completed
        supabase.table("ai_analyses").update({
            "status": "completed",
            "progress": 100,
            "completed_at": "now()"
        }).eq("id", analysis_id).execute()
        
        logger.info(f"AI analysis completed for {analysis_id}")
        
    except Exception as e:
        logger.error(f"AI analysis failed for {analysis_id}: {str(e)}")
        
        # Update status to error
        supabase.table("ai_analyses").update({
            "status": "error",
            "error_message": str(e)
        }).eq("id", analysis_id).execute()

async def cleanup_old_scans(user_id: str, keep_count: int = 5):
    """Clean up old scans, keeping only the most recent ones"""
    try:
        logger.info(f"Starting cleanup for user {user_id}, keeping {keep_count} scans")
        
        # Get old scans to delete
        old_scans = supabase.table("drive_scans").select("id").eq(
            "user_id", user_id
        ).order("created_at", desc=False).limit(100).execute()
        
        if len(old_scans.data) > keep_count:
            scans_to_delete = old_scans.data[:-keep_count]
            scan_ids = [scan['id'] for scan in scans_to_delete]
            
            # Delete related data (CASCADE will handle this)
            supabase.table("drive_scans").delete().in_("id", scan_ids).execute()
            
            logger.info(f"Cleaned up {len(scan_ids)} old scans for user {user_id}")
        else:
            logger.info(f"No cleanup needed for user {user_id}, only {len(old_scans.data)} scans found")
            
    except Exception as e:
        logger.error(f"Cleanup failed for user {user_id}: {e}")

async def _apply_ai_proposal(service, proposal_data: Dict) -> Dict:
    """Apply AI proposal to Google Drive"""
    results = {
        "successful_moves": [],
        "failed_moves": [],
        "created_folders": []
    }
    
    try:
        # Create folders and track their IDs
        folder_map = {}
        for folder in proposal_data["proposed_folders"]:
            try:
                folder_id = await _ensure_folder_exists(service, folder["name"])
                folder_map[folder["name"]] = folder_id
                results["created_folders"].append({
                    "name": folder["name"],
                    "id": folder_id
                })
            except Exception as e:
                logger.error(f"Failed to create folder {folder['name']}: {str(e)}")
        
        # Move files
        for move in proposal_data["file_moves"]:
            try:
                target_folder_id = folder_map.get(move["proposed_folder"])
                if target_folder_id:
                    await move_item(service, move["file_id"], target_folder_id)
                    results["successful_moves"].append(move["file_id"])
                else:
                    results["failed_moves"].append({
                        "file_id": move["file_id"],
                        "error": f"Target folder '{move['proposed_folder']}' not found"
                    })
            except Exception as e:
                results["failed_moves"].append({
                    "file_id": move["file_id"],
                    "error": str(e)
                })
        
        return results
        
    except Exception as e:
        logger.error(f"Failed to apply AI proposal: {str(e)}")
        raise e

async def _ensure_folder_exists(service, folder_name: str, parent_id: str = None) -> str:
    """Ensure folder exists, create if it doesn't"""
    try:
        # Try to find existing folder
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        if parent_id:
            query += f" and '{parent_id}' in parents"
        
        results = service.files().list(q=query, fields="files(id,name)").execute()
        files = results.get('files', [])
        
        if files:
            return files[0]['id']
        
        # Create new folder
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        if parent_id:
            folder_metadata['parents'] = [parent_id]
        
        folder = service.files().create(body=folder_metadata, fields='id').execute()
        return folder['id']
        
    except Exception as e:
        logger.error(f"Failed to ensure folder exists: {str(e)}")
        raise e

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3030) 