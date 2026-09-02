"""Launch the knowledge block FastAPI app."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "ki_knowledge.api.knowledge_app:app",
        host="0.0.0.0",
        port=8090,
        reload=True,
    )
