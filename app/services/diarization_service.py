import logging
import numpy as np
from pyannote.audio import Pipeline
import torch
from typing import List, Dict, Optional
from huggingface_hub import HfFolder, snapshot_download
from collections import deque

logger = logging.getLogger(__name__)

class DiarizationService:
    def __init__(self):
        self.pipeline: Optional[Pipeline] = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.audio_buffer = deque(maxlen=16000 * 30)
        self.initialize_pipeline()

    def initialize_pipeline(self):
        try:
            token = HfFolder.get_token()
            if not token:
                logger.error("""
                No HuggingFace token found. Please:
                1. Run 'huggingface-cli login' in your terminal
                2. Enter your token when prompted
                3. Restart the application
                """)
                return

            try:
                logger.info("Pre-downloading segmentation model...")
                snapshot_download(
                    "pyannote/segmentation-3.0",
                    use_auth_token=token,
                    local_files_only=False
                )
                logger.info("Successfully downloaded segmentation model")
            except Exception as e:
                if "gated" in str(e).lower():
                    logger.error("""
                    Access to the segmentation model is gated. Please:
                    1. Visit https://huggingface.co/pyannote/segmentation-3.0
                    2. Accept the user conditions
                    3. Restart the application
                    """)
                else:
                    logger.error(f"Error downloading segmentation model: {str(e)}")
                return

            try:
                logger.info("Attempting to load diarization pipeline...")
                self.pipeline = Pipeline.from_pretrained(
                    "pyannote/speaker-diarization-3.1",
                    use_auth_token=token
                )
                logger.info("Successfully loaded diarization pipeline")
            except Exception as e:
                if "gated" in str(e).lower():
                    logger.error("""
                    Access to the speaker diarization model is gated. Please:
                    1. Visit https://huggingface.co/pyannote/speaker-diarization-3.1
                    2. Accept the user conditions
                    3. Restart the application
                    """)
                else:
                    logger.error(f"Error loading diarization pipeline: {str(e)}")
                return

            if self.pipeline is None:
                logger.error("Failed to initialize diarization pipeline")
                return

            self.pipeline = self.pipeline.to(self.device)
            logger.info(f"Diarization pipeline loaded on {self.device}")
            
        except Exception as e:
            logger.error(f"Error in diarization initialization: {str(e)}")
            self.pipeline = None

    def process_audio(self, audio_data: np.ndarray, sample_rate: int) -> List[Dict]:
        """
        Process audio data and return speaker segments.
        Returns a list of dictionaries with speaker labels and timestamps.
        """
        if self.pipeline is None:
            logger.warning("Diarization pipeline not initialized, returning empty segments")
            return []

        try:
            self.audio_buffer.extend(audio_data.tolist())
            
            accumulated_audio = np.array(list(self.audio_buffer))
            
            if len(accumulated_audio) < sample_rate * 5:
                return []

            waveform = torch.from_numpy(accumulated_audio).float()
            if len(waveform.shape) == 1:
                waveform = waveform.unsqueeze(0)

            waveform = waveform.to(self.device)

            diarization = self.pipeline(
                {"waveform": waveform, "sample_rate": sample_rate},
                min_speakers=1,
                max_speakers=2
            )

            segments = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                if turn.end >= (len(accumulated_audio) - len(audio_data)) / sample_rate:
                    segments.append({
                        "speaker": speaker,
                        "start": turn.start,
                        "end": turn.end
                    })

            return segments

        except Exception as e:
            logger.error(f"Error in diarization: {str(e)}")
            return []

diarization_service = DiarizationService() 