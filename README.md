# Real-Time Conversation Transcription System

A real-time audio transcription system that captures conversations, transcribes them using OpenAI's Whisper model, identifies speakers, and provides an interactive web interface for playback and review.

## Features

- Real-time audio capture and transcription using OpenAI's Whisper
- Speaker diarization (speaker identification) using pyannote.audio
- Interactive web interface with:
  - Live transcription updates
  - Speaker identification (Speaker 1, Speaker 2)
  - Clickable segments for audio playback
  - Session management
  - Modern UI with Tailwind CSS

## Prerequisites

- Python 3.12 or higher
- Node.js 18 or higher
- CUDA-capable GPU (recommended for faster transcription)
- HuggingFace account with access token (for speaker diarization)
- Git

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd ai-transcriber-python
```

2. Create and activate a Python virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Linux/Mac
# OR
.\venv\Scripts\activate  # On Windows
```

3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

4. Install frontend dependencies and build:
```bash
cd clientApp
npm install
npm run build
cd ..  # Return to project root
```

5. Get your HuggingFace access token:
   - Create an account at https://huggingface.co/
   - Go to your profile settings
   - Create a new access token
   - Accept the user agreement for pyannote/speaker-diarization
   - Set the token as an environment variable:
```bash
export HUGGINGFACE_TOKEN="your-token-here"  # On Linux/Mac
# OR
set HUGGINGFACE_TOKEN=your-token-here  # On Windows
```

6. Install system dependencies (Ubuntu/Debian):
```bash
sudo apt-get update
sudo apt-get install -y portaudio19-dev python3-pyaudio
```

## Usage

1. Start the backend server:
```bash
# Make sure you're in the project root directory
# Make sure your virtual environment is activated
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

2. The frontend is already built and served by the backend server at http://localhost:8000

3. Open your web browser and navigate to http://localhost:8000

4. Allow microphone access when prompted

5. Start recording:
   - Click the "Start Recording" button
   - Speak into your microphone
   - The transcription will appear in real-time
   - Speakers will be automatically identified
   - Click on any segment to play back that part of the audio
   - Click "Stop Recording" when finished

## Project Structure

```
ai-transcriber-python/
├── app/
│   ├── api/
│   │   └── websocket.py      # WebSocket endpoints
│   ├── core/
│   │   └── websocket.py      # WebSocket manager
│   ├── services/
│   │   ├── audio_service.py  # Audio processing and transcription
│   │   └── diarization_service.py  # Speaker identification
│   └── main.py              # FastAPI application
├── clientApp/
│   ├── src/
│   │   ├── components/      # Vue components
│   │   ├── composables/     # Vue composables
│   │   └── App.vue          # Main Vue application
│   ├── package.json         # Frontend dependencies
│   └── vite.config.ts       # Vite configuration
├── recordings/              # Stored audio recordings
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

## Technical Details

### Backend
- FastAPI for the web server
- WebSocket for real-time communication
- OpenAI Whisper for transcription
- pyannote.audio for speaker diarization
- soundfile for audio processing

### Frontend
- Vue.js 3 with Composition API
- Tailwind CSS for styling
- WebSocket for real-time updates
- Web Audio API for playback

## Troubleshooting

1. If you get a "Module not found" error:
   - Make sure you're in the correct directory
   - Verify that your virtual environment is activated
   - Try reinstalling dependencies: `pip install -r requirements.txt`

2. If the frontend doesn't load:
   - Check that you've run `npm install` and `npm run build` in the clientApp directory
   - Verify that the backend server is running
   - Check the browser console for errors

3. If transcription is slow:
   - Ensure you have a CUDA-capable GPU
   - Check that PyTorch is using CUDA: `python -c "import torch; print(torch.cuda.is_available())"`
   - Consider using a smaller Whisper model (e.g., "tiny" instead of "base")

4. If speaker diarization fails:
   - Verify your HuggingFace token is set correctly
   - Check that you've accepted the user agreement for pyannote/speaker-diarization
   - Look for error messages in the backend logs

## License

This project is licensed under the MIT License. 