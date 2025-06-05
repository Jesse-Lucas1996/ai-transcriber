<template>
    <div class="recording-interface">
        <div class="recording-container">
            <div class="card status-bar">
                <div class="status-controls">
                    <button
                        @click="toggleRecording"
                        class="btn"
                        :class="isRecording ? 'btn-danger' : 'btn-primary'"
                    >
                        {{ isRecording ? 'Stop Recording' : 'Start Recording' }}
                    </button>
                    <div class="connection-status">
                        <div
                            class="status-indicator"
                            :class="isConnected ? 'status-connected' : 'status-disconnected'"
                        ></div>
                        <span class="text-light">
                            {{ isConnected ? 'Connected' : 'Disconnected' }}
                        </span>
                    </div>
                </div>
                <div v-if="error" class="text-error">
                    {{ error }}
                </div>
            </div>

            <div class="card transcript-container">
                <div v-for="(transcription, index) in transcriptions" 
                     :key="index" 
                     class="transcription-group">
                    <div v-for="(segment, segIndex) in transcription.segments" 
                         :key="segIndex" 
                         class="transcript-segment"
                         @click="playSegment(transcription.session_id, segment)">
                        <div class="segment-content">
                            <span
                                class="speaker-tag"
                                :class="getSpeakerClass(segment.speaker)"
                            >
                                {{ formatSpeaker(segment.speaker) }}
                            </span>
                            <span class="segment-text">{{ segment.text }}</span>
                        </div>
                        <div class="segment-meta">
                            <span class="text-light">{{ formatTime(segment.start) }} - {{ formatTime(segment.end) }}</span>
                            <button 
                                v-if="isPlayingSegment(segment)"
                                @click.stop="stopPlayback"
                                class="btn btn-primary btn-sm"
                            >
                                Stop
                            </button>
                        </div>
                    </div>
                </div>
                <div v-if="transcriptions.length === 0" class="empty-state text-center text-light">
                    {{ isRecording ? 'Listening...' : 'Click Start Recording to begin' }}
                </div>
            </div>
        </div>

        <audio ref="audioPlayer" @ended="onPlaybackEnded" class="hidden"></audio>
    </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useAudioRecorder } from '../composables/useAudioRecorder'
import { useWebSocket } from '../composables/useWebSocket'
import type { Transcription, WebSocketMessage } from '../composables/useWebSocket'

interface TranscriptionSegment {
    text: string
    speaker: string
    start: number
    end: number
    absolute_start: number
    absolute_end: number
}

interface TranscriptionWithSession extends Transcription {
    session_id: string
}

const transcriptions = ref<TranscriptionWithSession[]>([])
const error = ref<string | null>(null)
const isRecordingSessionActive = ref(false)
const audioPlayer = ref<HTMLAudioElement | null>(null)
const currentPlayingSegment = ref<TranscriptionSegment | null>(null)

const { 
    isRecording,
    startRecording: startAudioRecording,
    stopRecording: stopAudioRecording,
    setAudioDataCallback,
    error: recorderError
} = useAudioRecorder()

const {
    isConnected,
    lastMessage,
    sendMessage,
    startRecording: startWebSocketRecording,
    stopRecording: stopWebSocketRecording,
    error: wsError
} = useWebSocket('ws://localhost:8000/ws')

watch([recorderError, wsError], ([newRecorderError, newWsError]) => {
    error.value = newRecorderError || newWsError
})

async function toggleRecording() {
    try {
        if (isRecording.value) {
            stopAudioRecording()
            stopWebSocketRecording()
            isRecordingSessionActive.value = false
        } else {
            await startWebSocketRecording()
            sendMessage({ type: 'start_recording' })
            await new Promise(resolve => setTimeout(resolve, 100))
            await startAudioRecording()
            isRecordingSessionActive.value = true
        }
    } catch (err) {
        console.error('Error toggling recording:', err)
        error.value = err instanceof Error ? err.message : 'Failed to toggle recording'
        stopAudioRecording()
        stopWebSocketRecording()
        isRecordingSessionActive.value = false
    }
}

onMounted(() => {
    setAudioDataCallback(({ type, data }) => {
        if (isConnected.value && isRecording.value && isRecordingSessionActive.value && type === 'chunk') {
            sendMessage({
                type: 'audio_data',
                audio: data
            })
        }
    })
})

watch(lastMessage, (message: WebSocketMessage | null) => {
    if (!message) return

    switch (message.type) {
        case 'transcription':
            if (message.text && message.session_id) {
                transcriptions.value.push({
                    type: 'transcription',
                    text: message.text,
                    timestamp: Date.now(),
                    duration: 0,
                    segments: message.segments?.map(seg => ({
                        text: seg.text,
                        speaker: seg.speaker,
                        start: seg.start,
                        end: seg.end,
                        absolute_start: seg.absolute_start,
                        absolute_end: seg.absolute_end
                    })) || [],
                    session_id: message.session_id
                })
            }
            break

        case 'audio_segment':
            if (audioPlayer.value && message.audio) {
                try {
                    console.log('Received audio segment:', {
                        sessionId: message.session_id,
                        start: message.start_time,
                        end: message.end_time,
                        audioLength: message.audio.length
                    })
                    
                    const audioBlob = new Blob(
                        [Uint8Array.from(atob(message.audio), c => c.charCodeAt(0))],
                        { type: 'audio/wav' }
                    )
                    const audioUrl = URL.createObjectURL(audioBlob)
                    
                    if (audioPlayer.value.src) {
                        URL.revokeObjectURL(audioPlayer.value.src)
                    }
                    
                    audioPlayer.value.src = audioUrl
                    audioPlayer.value.play().catch(err => {
                        console.error('Error playing audio:', err)
                        error.value = 'Failed to play audio: ' + (err instanceof Error ? err.message : String(err))
                        stopPlayback()
                    })
                } catch (err) {
                    console.error('Error processing audio segment:', err)
                    error.value = err instanceof Error ? err.message : 'Failed to process audio segment'
                    stopPlayback()
                }
            } else {
                console.warn('Missing audio data or player element')
                error.value = 'Missing audio data or player element'
            }
            break

        case 'error':
            console.error('WebSocket error:', message.error)
            error.value = message.error || 'Unknown error occurred'
            if (message.error?.includes('No active recording session')) {
                isRecordingSessionActive.value = false
            }
            break

        case 'status':
            if (message.status === 'recording_started') {
                isRecordingSessionActive.value = true
            } else if (message.status === 'recording_stopped') {
                isRecordingSessionActive.value = false
            }
            break
    }
})

function playSegment(sessionId: string, segment: TranscriptionSegment) {
    if (currentPlayingSegment.value === segment) {
        stopPlayback()
        return
    }

    try {
        currentPlayingSegment.value = segment
        console.log('Requesting audio segment:', {
            sessionId,
            start: segment.absolute_start,
            end: segment.absolute_end
        })
        
        sendMessage({
            type: 'play_audio',
            session_id: sessionId,
            start_time: segment.absolute_start,
            end_time: segment.absolute_end
        })
    } catch (err) {
        console.error('Error playing segment:', err)
        error.value = err instanceof Error ? err.message : 'Failed to play audio segment'
        currentPlayingSegment.value = null
    }
}

function stopPlayback() {
    if (audioPlayer.value) {
        audioPlayer.value.pause()
        audioPlayer.value.currentTime = 0
    }
    currentPlayingSegment.value = null
}

function onPlaybackEnded() {
    currentPlayingSegment.value = null
}

function isPlayingSegment(segment: TranscriptionSegment) {
    return currentPlayingSegment.value === segment
}

function formatTime(seconds: number): string {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
}

function formatSpeaker(speaker: string): string {
    return speaker.replace('SPEAKER_', 'Speaker ')
}

function getSpeakerClass(speaker: string): string {
    return speaker === 'SPEAKER_1' 
        ? 'speaker-1' 
        : 'speaker-2'
}

onUnmounted(() => {
    stopPlayback()
})
</script>

<style scoped>
.recording-interface {
    width: 100%;
    max-width: 800px;
    margin: 0 auto;
}

.recording-container {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-lg);
}

.status-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--spacing-md);
}

.status-controls {
    display: flex;
    align-items: center;
    gap: var(--spacing-lg);
}

.connection-status {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
}

.status-indicator {
    width: 12px;
    height: 12px;
    border-radius: var(--radius-full);
}

.status-connected {
    background-color: var(--color-success);
}

.status-disconnected {
    background-color: var(--color-error);
}

.transcript-container {
    max-height: 70vh;
    overflow-y: auto;
    padding: var(--spacing-md);
}

.transcription-group {
    margin-bottom: var(--spacing-lg);
}

.transcription-group:last-child {
    margin-bottom: 0;
}

.transcript-segment {
    padding: var(--spacing-md);
    border-bottom: 1px solid var(--color-border);
    cursor: pointer;
    transition: var(--transition-base);
}

.transcript-segment:hover {
    background-color: var(--color-background);
}

.transcript-segment:last-child {
    border-bottom: none;
}

.segment-content {
    display: flex;
    gap: var(--spacing-md);
    margin-bottom: var(--spacing-xs);
}

.speaker-tag {
    padding: var(--spacing-xs) var(--spacing-sm);
    border-radius: var(--radius-md);
    font-size: var(--font-size-sm);
    font-weight: 500;
    flex-shrink: 0;
}

.speaker-1 {
    background-color: #dbeafe;
    color: #1e40af;
}

.speaker-2 {
    background-color: #dcfce7;
    color: #166534;
}

.segment-text {
    flex-grow: 1;
    line-height: 1.5;
}

.segment-meta {
    display: flex;
    align-items: center;
    gap: var(--spacing-md);
    margin-left: calc(var(--spacing-md) * 2);
    font-size: var(--font-size-sm);
}

.btn-sm {
    padding: var(--spacing-xs) var(--spacing-sm);
    font-size: var(--font-size-sm);
}

.empty-state {
    padding: var(--spacing-2xl) 0;
}

.hidden {
    display: none;
}

@media (prefers-color-scheme: dark) {
    .speaker-1 {
        background-color: #1e3a8a;
        color: #93c5fd;
    }

    .speaker-2 {
        background-color: #14532d;
        color: #86efac;
    }

    .transcript-segment:hover {
        background-color: var(--color-card-dark-mode);
    }
}
</style>