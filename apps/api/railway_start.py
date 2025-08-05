#!/usr/bin/env python3
"""
Railway startup script for Drive Organizer API
"""
import os
import sys
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables
from dotenv import load_dotenv

# Try to load from multiple possible locations
env_files = [
    ".env",
    "../../.env",
    "/app/.env"
]

for env_file in env_files:
    if os.path.exists(env_file):
        load_dotenv(env_file)
        break

# Import and run the FastAPI app
from main import app

if __name__ == "__main__":
    import uvicorn
    
    # Get port from environment (Railway sets PORT)
    port = int(os.getenv("PORT", 3030))
    host = os.getenv("HOST", "0.0.0.0")
    
    print(f"Starting Drive Organizer API on {host}:{port}")
    print(f"PORT environment variable: {os.getenv('PORT', 'not set')}")
    print(f"All environment variables: {dict(os.environ)}")
    uvicorn.run(app, host=host, port=port) 