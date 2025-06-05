import json
import logging
import base64
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.websocket import manager
from app.services.audio_service import audio_service

logger = logging.getLogger(__name__)
router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    logger.info("WebSocket client connected")
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                message_type = message.get("type")
                logger.debug(f"Received WebSocket message type: {message_type}")
                
                if message_type == "start_recording":
                    session_id = audio_service.start_recording_session()
                    response = {
                        "type": "status",
                        "status": "recording_started",
                        "session_id": session_id
                    }
                    logger.info(f"Starting recording session: {session_id}")
                    await websocket.send_json(response)
                    
                elif message_type == "stop_recording":
                    audio_service.stop_recording_session()
                    response = {
                        "type": "status",
                        "status": "recording_stopped"
                    }
                    logger.info("Stopping recording session")
                    await websocket.send_json(response)
                    
                elif message_type == "audio_data":
                    audio_data = message.get("audio")
                    if not audio_data:
                        logger.error("Missing audio data in message")
                        raise ValueError("Missing audio data")
                    
                    logger.debug("Processing audio chunk")
                    result = await audio_service.process_audio_chunk(audio_data)
                    logger.info(f"Sending WebSocket response: {result}")
                    await websocket.send_json(result)

                elif message_type == "play_audio":
                    session_id = message.get("session_id")
                    start_time = message.get("start_time")
                    end_time = message.get("end_time")
                    
                    if not all([session_id, start_time, end_time]):
                        raise ValueError("Missing required parameters for audio playback")
                    
                    audio_segment = await audio_service.get_audio_segment(
                        session_id, float(start_time), float(end_time)
                    )
                    
                    if audio_segment:
                        audio_base64 = base64.b64encode(audio_segment).decode('utf-8')
                        response = {
                            "type": "audio_segment",
                            "session_id": session_id,
                            "start_time": start_time,
                            "end_time": end_time,
                            "audio": audio_base64
                        }
                        await websocket.send_json(response)
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Audio segment not found"
                        })

                elif message_type == "status":
                    status = message.get("status")
                    if status == "start_recording":
                        session_id = audio_service.start_recording_session()
                        response = {
                            "type": "status",
                            "status": "recording_started",
                            "session_id": session_id
                        }
                        logger.info(f"Starting recording session: {session_id}")
                        await websocket.send_json(response)
                    elif status == "stop_recording":
                        audio_service.stop_recording_session()
                        response = {
                            "type": "status",
                            "status": "recording_stopped"
                        }
                        logger.info("Stopping recording session")
                        await websocket.send_json(response)
                    else:
                        logger.warning(f"Unknown status: {status}")
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Unknown status: {status}"
                        })
                    
                else:
                    error_msg = f"Unknown message type: {message_type}"
                    logger.warning(error_msg)
                    await websocket.send_json({
                        "type": "error",
                        "message": error_msg
                    })
                    
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON received: {str(e)}")
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON message"
                })
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {str(e)}")
                await websocket.send_json({
                    "type": "error",
                    "message": f"Error processing message: {str(e)}"
                })
                
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        manager.disconnect(websocket) 