"""Main FastAPI application for Drive Organizer."""

import os
import uuid
from typing import Dict, List
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
    mime_type: str
    size: int = 0
    created_time: str
    modified_time: str
    parents: List[str] = []
    web_view_link: str = ""

class DriveFolder(BaseModel):
    """Model for Google Drive folder."""
    id: str
    name: str
    created_time: str
    modified_time: str
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
    error_message: str = None
    completed_at: str = None

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
            "expires_at": (time.time() + data["expires_in"]).isoformat() + "Z"
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
        
        file_count = 0
        folder_count = 0
        all_files = []
        all_folders = []
        
        # Scan files if requested
        if include_files:
            files_result = list_files(service, max_results=max_results)
            all_files = files_result.get("files", [])
            file_count = len(all_files)
            
            # Store file metadata
            supabase.table("drive_files").insert({
                "scan_id": scan_id,
                "user_id": user_id,
                "files": all_files
            }).execute()
        
        # Scan folders if requested
        if include_folders:
            folders_result = list_files(service, 
                                      max_results=max_results,
                                      mime_type="application/vnd.google-apps.folder")
            all_folders = folders_result.get("files", [])
            folder_count = len(all_folders)
            
            # Store folder metadata
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3030) 