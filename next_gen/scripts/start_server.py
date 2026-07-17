#!/usr/bin/env python3
"""Start the BCREC AI Receptionist server."""

import os
import sys
from pathlib import Path

# Add next_gen to path
NEXT_GEN_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(NEXT_GEN_DIR))

# Load .env if exists
env_file = NEXT_GEN_DIR / "config" / ".env"
if env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(env_file)

# Import and run
import uvicorn
from src.main import app

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    print(f"Starting BCREC AI Receptionist on {host}:{port}")
    print(f"Frontend: http://localhost:5173 (run 'npm run dev' in frontend/)")
    print(f"API: http://localhost:{port}/api/health")
    uvicorn.run(app, host=host, port=port)
