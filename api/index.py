import sys
from pathlib import Path

# Explicitly ensure backend directory is discoverable in Python sys.path
api_dir = Path(__file__).resolve().parent
root_dir = api_dir.parent
backend_dir = root_dir / "backend"

if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

# Import the core FastAPI instance
from backend.main import app

# Export the ASGI application for Vercel Serverless Functions
__all__ = ["app"]
