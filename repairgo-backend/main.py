import asyncio
import os
from datetime import datetime, timedelta

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from routes.technician_routes import router as tech_router
from routes.service_routes import router as service_router
from routes.user_routes import router as user_router
from routes.admin_routes import router as admin_router
from routes.ml_routes import router as ml_router
from routes.profile_routes import router as profile_router
from utils.reassignment_utils import reassign_stale_jobs
from utils.exception_handler import setup_exception_handlers
from utils.response_utils import success_response
from utils.background_job_monitor import job_monitor
from utils.logger import logger
from utils.websocket_manager import ws_manager
from utils.jwt_utils import decode_access_token
from utils.auth_utils import require_roles
from utils.model_download import download_models_if_needed

load_dotenv()

app = FastAPI()

frontend_url = os.getenv("FRONTEND_URL", "")

allowed_origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://localhost:5176",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175",
    "http://127.0.0.1:5176",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://repair-go.vercel.app",
    "https://repair-go-git-main-vigneshwars-projects-ea6ead1c.vercel.app",
]
allowed_origins.extend([origin.strip() for origin in frontend_url.split(",") if origin.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dict.fromkeys(allowed_origins)),
    allow_origin_regex=r"^https://.*\.vercel\.app$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.options("/{full_path:path}")
def preflight_handler(full_path: str) -> Response:
    return Response(status_code=204)

setup_exception_handlers(app)

app.include_router(tech_router)
app.include_router(user_router)
app.include_router(service_router)
app.include_router(admin_router)
app.include_router(ml_router)
app.include_router(profile_router)


async def reassign_stale_loop() -> None:
    """Background task for auto-reassigning stale job assignments."""
    while True:
        try:
            job_monitor.start_execution()
            start_time = datetime.utcnow()
            
            reassigned, attempted = reassign_stale_jobs(stale_minutes=5)
            
            execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            metrics = {
                "reassigned": reassigned,
                "attempted": attempted,
                "execution_time_ms": execution_time_ms,
            }
            job_monitor.complete_execution(metrics)
            logger.info(f"Stale job reassignment completed: {metrics}")
            
        except Exception as e:
            error_msg = str(e)
            job_monitor.fail_execution(error_msg)
            logger.error(f"Stale job reassignment failed: {error_msg}")
        
        # Schedule next execution in 60 seconds
        next_run = datetime.utcnow() + timedelta(seconds=60)
        job_monitor.set_next_execution(next_run)
        await asyncio.sleep(60)


@app.on_event("startup")
async def start_reassign_loop() -> None:
    """Initialize background task on application startup."""
    download_models_if_needed()
    asyncio.create_task(reassign_stale_loop())
    logger.info("Background job monitor initialized")


@app.get("/")
def root():
    return success_response("RepairGo Backend Running 🚀")

@app.websocket("/ws/notifications/{user_id}")
async def websocket_notifications(
    websocket: WebSocket,
    user_id: str,
    token: str = Query(...),
):
    """
    WebSocket endpoint for real-time notifications.
    
    Connect with: ws://host/ws/notifications/{user_id}?token=JWT_TOKEN
    
    Receives JSON messages:
    {
        "type": "notification",
        "event_type": "assignment|status_update|cancellation|...",
        "message": "...",
        "related_id": "service_id",
        "context": {...},
        "timestamp": "ISO datetime"
    }
    """
    try:
        payload = decode_access_token(token)
        token_user_id = payload.get("sub")
        if token_user_id != user_id:
            await websocket.close(code=1008, reason="WebSocket token does not match requested user")
            return
    except Exception as e:
        logger.warning(f"WebSocket auth failed for user_id={user_id}: {e}")
        await websocket.close(code=1008, reason="Invalid or expired token")
        return
    
    await ws_manager.connect(websocket, user_id)
    
    try:
        while True:
            # Keep connection alive, handle client messages if needed
            data = await websocket.receive_text()
            
            # Handle ping/pong for connection keep-alive
            if data == "ping":
                await websocket.send_text("pong")
            # Could add more client message handling here
            
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, user_id)
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
        ws_manager.disconnect(websocket, user_id)


@app.get("/ws/stats")
def websocket_stats(user=Depends(require_roles("admin"))):
    """Get WebSocket connection statistics."""
    return success_response("WebSocket stats", ws_manager.get_stats())
