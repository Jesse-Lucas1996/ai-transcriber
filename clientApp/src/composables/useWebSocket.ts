import { ref, onUnmounted, Ref } from 'vue'

export interface TranscriptionSegment {
    text: string
    speaker: string
    start: number
    end: number
    absolute_start: number
    absolute_end: number
}

export interface Transcription {
    type: 'transcription'
    text: string
    timestamp: number
    duration: number
    segments: TranscriptionSegment[]
    session_id: string
}

export interface WebSocketMessage {
    type: 'transcription' | 'audio_data' | 'error' | 'status' | 'start_recording' | 'stop_recording' | 'audio_segment' | 'play_audio'
    // Transcription fields
    text?: string
    timestamp?: number
    duration?: number
    segments?: TranscriptionSegment[]
    session_id?: string
    // Audio data fields
    audio?: string
    // Audio playback fields
    start_time?: number
    end_time?: number
    // Error and status fields
    error?: string
    status?: string
}

export interface UseWebSocketReturn {
    isConnected: Ref<boolean>
    lastMessage: Ref<WebSocketMessage | null>
    error: Ref<string | null>
    sendMessage: (message: WebSocketMessage) => void
    startRecording: () => Promise<void>
    stopRecording: () => void
}

export function useWebSocket(url: string): UseWebSocketReturn {
    const isConnected = ref(false)
    const lastMessage = ref<WebSocketMessage | null>(null)
    const error = ref<string | null>(null)
    let ws: WebSocket | null = null

    function connect() {
        return new Promise<void>((resolve, reject) => {
            try {
                ws = new WebSocket(url)

                ws.onopen = () => {
                    isConnected.value = true
                    error.value = null
                    resolve()
                }

                ws.onclose = () => {
                    isConnected.value = false
                    ws = null
                }

                ws.onerror = () => {
                    error.value = 'WebSocket connection error'
                    reject(new Error('WebSocket connection error'))
                }

                ws.onmessage = (event) => {
                    try {
                        const message = JSON.parse(event.data) as WebSocketMessage
                        lastMessage.value = message
                    } catch (err) {
                        console.error('Error parsing WebSocket message:', err)
                        error.value = 'Invalid message format'
                    }
                }
            } catch (err) {
                error.value = 'Failed to connect to WebSocket'
                reject(err)
            }
        })
    }

    function disconnect() {
        if (ws) {
            ws.close()
            ws = null
        }
    }

    function sendMessage(message: WebSocketMessage) {
        if (!ws || ws.readyState !== WebSocket.OPEN) {
            error.value = 'WebSocket is not connected'
            return
        }
        ws.send(JSON.stringify(message))
    }

    async function startRecording() {
        if (!isConnected.value) {
            await connect()
        }
        sendMessage({ type: 'status', status: 'start_recording' })
    }

    function stopRecording() {
        if (isConnected.value) {
            sendMessage({ type: 'status', status: 'stop_recording' })
        }
    }

    // Cleanup on component unmount
    onUnmounted(() => {
        disconnect()
    })

    return {
        isConnected,
        lastMessage,
        error,
        sendMessage,
        startRecording,
        stopRecording
    }
} 