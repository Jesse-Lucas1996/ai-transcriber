from http.client import HTTPException
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from app.core.logging import setup_logging
from app.api.websocket import router as websocket_router

setup_logging()

def create_app() -> FastAPI:
    app = FastAPI(title="Real-Time Transcription System")
    
    app.mount("/assets", StaticFiles(directory="clientApp/dist/assets"), name="assets")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.include_router(websocket_router)
    
    @app.get("/vite.svg")
    async def get_vite_svg():
        return FileResponse("clientApp/dist/vite.svg")
    
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str, request: Request):
        if full_path.startswith(("api/", "ws/")):
            raise HTTPException(status_code=404, detail="Not found")
        
        return FileResponse("clientApp/dist/index.html")
    
    return app

app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
