import base64
import logging
import numpy as np
import whisper
import torch
import asyncio
import json
import soundfile as sf
import os
from typing import Dict, Optional
from datetime import datetime
from .diarization_service import diarization_service

logger = logging.getLogger(__name__)

class AudioService:
    def __init__(self):
        self.sample_rate = 16000
        self.current_session: Optional[str] = None
        self.audio_buffer = []
        self.full_audio_buffer = []
        self.processing_lock = asyncio.Lock()
        self.whisper_model = None
        self.processing_task = None
        self.recording_start_time = None
        self.audio_dir = "recordings"
        self.session_start_times: Dict[str, float] = {}
        self.initialize_models()
        self._ensure_audio_dir()

    def _ensure_audio_dir(self):
        if not os.path.exists(self.audio_dir):
            os.makedirs(self.audio_dir)

    def initialize_models(self):
        try:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self.whisper_model = whisper.load_model("base", device=device)
            logger.info(f"Whisper model loaded on {device}")
        except Exception as e:
            logger.error(f"Error loading model: {str(e)}")
            raise

    def start_recording_session(self) -> str:
        self.current_session = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.audio_buffer = []
        self.full_audio_buffer = []
        self.recording_start_time = datetime.now()
        self.session_start_times[self.current_session] = self.recording_start_time.timestamp()
        logger.info(f"Started new recording session: {self.current_session} at {self.session_start_times[self.current_session]}")
        return self.current_session

    def stop_recording_session(self) -> None:
        if self.audio_buffer:
            asyncio.create_task(self._process_buffer(final=True))
        if self.full_audio_buffer:
            self._save_recording()
        logger.info(f"Stopped recording session: {self.current_session}")
        self.current_session = None
        self.audio_buffer = []
        self.full_audio_buffer = []
        self.recording_start_time = None

    def _save_recording(self):
        if not self.current_session:
            logger.warning("Attempted to save recording without an active session")
            return
        try:
            audio_data = np.array(self.full_audio_buffer)
            filename = os.path.join(self.audio_dir, f"{self.current_session}.wav")
            sf.write(filename, audio_data, self.sample_rate)
            logger.info(f"Saved recording to {filename}")
        except Exception as e:
            logger.error(f"Error saving recording: {str(e)}")

    def _get_session_start_time(self, session_id: str) -> Optional[float]:
        return self.session_start_times.get(session_id)

    async def get_audio_segment(self, session_id: str, start_time: float, end_time: float) -> Optional[bytes]:
        try:
            filename = os.path.join(self.audio_dir, f"{session_id}.wav")
            logger.info(f"Attempting to get audio segment from {filename} between {start_time}s and {end_time}s")
            
            if not os.path.exists(filename):
                logger.error(f"Audio file not found: {filename}")
                return None

            session_start = self._get_session_start_time(session_id)
            if session_start is None:
                logger.error(f"No start time found for session {session_id}")
                return None

            relative_start = start_time - session_start
            relative_end = end_time - session_start
            logger.info(f"Session start: {session_start}, Converted to relative timestamps: {relative_start}s to {relative_end}s")

            audio_data, sr = sf.read(filename)
            if sr != self.sample_rate:
                logger.warning(f"Sample rate mismatch: file has {sr}Hz, expected {self.sample_rate}Hz")

            start_sample = int(relative_start * sr)
            end_sample = int(relative_end * sr)
            
            if start_sample < 0 or end_sample > len(audio_data):
                logger.error(f"Invalid time range: {relative_start}s to {relative_end}s (file duration: {len(audio_data)/sr:.2f}s)")
                return None
                
            if start_sample >= end_sample:
                logger.error(f"Invalid time range: start time ({relative_start}s) >= end time ({relative_end}s)")
                return None

            segment = audio_data[start_sample:end_sample]
            
            import tempfile
            import io
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                sf.write(temp_file.name, segment, sr, format='WAV')
                with open(temp_file.name, 'rb') as f:
                    wav_bytes = f.read()
                os.unlink(temp_file.name)
            
            logger.info(f"Successfully created WAV segment of {len(wav_bytes)} bytes")
            return wav_bytes

        except Exception as e:
            logger.error(f"Error getting audio segment: {str(e)}", exc_info=True)
            return None

    async def process_audio_chunk(self, audio_data: str) -> Dict:
        try:
            audio_bytes = base64.b64decode(audio_data)
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
            audio_float = audio_array.astype(np.float32) / 32768.0
            
            if len(audio_float) > 0:
                audio_float = audio_float[::3]
                self.audio_buffer.extend(audio_float)
                self.full_audio_buffer.extend(audio_float)
            
            if len(self.audio_buffer) >= self.sample_rate:
                if self.processing_task is None or self.processing_task.done():
                    self.processing_task = asyncio.create_task(self._process_buffer())
                
            return {"type": "processing", "message": "Processing audio"}
                
        except Exception as e:
            logger.error(f"Error processing audio: {str(e)}")
            return {"type": "error", "message": str(e)}

    async def _process_buffer(self, final: bool = False) -> None:
        async with self.processing_lock:
            try:
                if not self.audio_buffer:
                    return

                audio_data = np.array(self.audio_buffer)
                
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.whisper_model.transcribe(
                        audio_data,
                        language="en",
                        fp16=False
                    )
                )

                speaker_segments = diarization_service.process_audio(
                    audio_data, 
                    self.sample_rate
                )

                buffer_offset = len(self.full_audio_buffer) / self.sample_rate - len(audio_data) / self.sample_rate

                processed_segments = []
                for segment in result["segments"]:
                    if segment["text"].strip():
                        speaker = "UNKNOWN"
                        segment_start = segment["start"] + buffer_offset
                        segment_end = segment["end"] + buffer_offset
                        
                        max_overlap = 0
                        for spk_seg in speaker_segments:
                            spk_start = spk_seg["start"] + buffer_offset
                            spk_end = spk_seg["end"] + buffer_offset
                            overlap = min(segment_end, spk_end) - max(segment_start, spk_start)
                            if overlap > max_overlap:
                                max_overlap = overlap
                                speaker = spk_seg["speaker"]

                        if self.recording_start_time:
                            abs_start = self.recording_start_time.timestamp() + segment_start
                            abs_end = self.recording_start_time.timestamp() + segment_end
                        else:
                            abs_start = segment_start
                            abs_end = segment_end

                        processed_segments.append({
                            "text": segment["text"],
                            "speaker": speaker,
                            "start": segment_start,
                            "end": segment_end,
                            "absolute_start": abs_start,
                            "absolute_end": abs_end
                        })

                if processed_segments:
                    from app.core.websocket import manager
                    message = {
                        "type": "transcription",
                        "text": " ".join(seg["text"] for seg in processed_segments),
                        "segments": processed_segments,
                        "session_id": self.current_session
                    }
                    await manager.broadcast(json.dumps(message))

                self.audio_buffer = []
                
            except Exception as e:
                logger.error(f"Error in transcription: {str(e)}")
            finally:
                self.processing_task = None

audio_service = AudioService()