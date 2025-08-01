"""Main FastAPI application for Drive Organizer."""

import os
import uuid
from typing import Dict, List
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import structlog
from supabase import create_client, Client
import openai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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

# Initialize Supabase client with error handling
try:
    supabase: Client = create_client(supabase_url, supabase_key)
except Exception as e:
    logger.warning(f"Failed to initialize Supabase client: {e}")
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

# Dependency to get current user
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    """Get current user from JWT token."""
    if supabase is None:
        raise HTTPException(status_code=503, detail="Authentication service unavailable")
    
    try:
        # Verify the JWT token with Supabase
        user = supabase.auth.get_user(credentials.credentials)
        return user.user
    except Exception as e:
        logger.error("Failed to authenticate user", error=str(e))
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "drive-organizer-api"}

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3030) 