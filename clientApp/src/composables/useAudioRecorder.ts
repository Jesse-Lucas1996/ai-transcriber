import { ref, onUnmounted, Ref } from 'vue'

export interface UseAudioRecorderReturn {
    isRecording: Ref<boolean>
    error: Ref<string | null>
    startRecording: () => Promise<void>
    stopRecording: () => void
    setAudioDataCallback: (callback: (audioData: { type: string, data: string, sampleRate: number }) => void) => void
}

export function useAudioRecorder(): UseAudioRecorderReturn {
    const isRecording = ref(false)
    const error = ref<string | null>(null)
    
    let audioContext: AudioContext | null = null
    let processor: ScriptProcessorNode | null = null
    let audioStream: MediaStream | null = null
    let onAudioData: ((audioData: { type: string, data: string, sampleRate: number }) => void) | null = null
    let audioBuffer: Float32Array | null = null
    const BUFFER_SIZE = 8192 // Increased buffer size for better quality
    const MIN_AMPLITUDE = 0.01 // Minimum amplitude threshold

    function cleanup() {
        if (processor) {
            processor.disconnect()
            processor = null
        }
        
        if (audioContext) {
            audioContext.close()
            audioContext = null
        }
        
        if (audioStream) {
            audioStream.getTracks().forEach(track => track.stop())
            audioStream = null
        }
        
        audioBuffer = null
        isRecording.value = false
    }

    async function startRecording() {
        try {
            cleanup()

            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,
                    sampleRate: 48000, // Match server's sample rate
                }
            })
            audioStream = stream

            // Create audio context and processor
            audioContext = new AudioContext({
                sampleRate: 48000,
                latencyHint: 'interactive'
            })
            const source = audioContext.createMediaStreamSource(stream)
            
            // Create script processor for chunked audio processing
            processor = audioContext.createScriptProcessor(BUFFER_SIZE, 1, 1)
            
            // Initialize audio buffer
            audioBuffer = new Float32Array(BUFFER_SIZE)
            let bufferPosition = 0
            
            // Process audio chunks
            processor.onaudioprocess = (e) => {
                if (!onAudioData || !audioBuffer) return

                const inputData = e.inputBuffer.getChannelData(0)
                
                // Apply simple noise gate and normalization
                let maxAmplitude = 0
                for (let i = 0; i < inputData.length; i++) {
                    const amplitude = Math.abs(inputData[i])
                    maxAmplitude = Math.max(maxAmplitude, amplitude)
                }
                
                // Only process if there's significant audio
                if (maxAmplitude > MIN_AMPLITUDE) {
                    // Normalize and apply noise gate
                    const scale = maxAmplitude > 0 ? 1 / maxAmplitude : 1
                    for (let i = 0; i < inputData.length; i++) {
                        const value = inputData[i] * scale
                        audioBuffer[bufferPosition++] = value
                    }
                    
                    // When buffer is full, send it
                    if (bufferPosition >= BUFFER_SIZE) {
                        const pcmData = new Int16Array(BUFFER_SIZE)
                        
                        // Convert float32 to int16
                        for (let i = 0; i < BUFFER_SIZE; i++) {
                            pcmData[i] = Math.max(-32768, Math.min(32767, Math.round(audioBuffer[i] * 32768)))
                        }

                        // Convert to base64
                        const base64Data = btoa(
                            Array.from(new Uint8Array(pcmData.buffer))
                                .map(byte => String.fromCharCode(byte))
                                .join('')
                        )
                        
                        onAudioData({
                            type: 'chunk',
                            data: base64Data,
                            sampleRate: audioContext?.sampleRate || 48000
                        })
                        
                        // Reset buffer
                        bufferPosition = 0
                        audioBuffer = new Float32Array(BUFFER_SIZE)
                    }
                }
            }

            // Connect the audio graph
            source.connect(processor)
            processor.connect(audioContext.destination)
            
            isRecording.value = true
            error.value = null

        } catch (err) {
            console.error('Error starting recording:', err)
            error.value = err instanceof Error ? err.message : 'Failed to start recording'
            cleanup()
            throw err
        }
    }

    function stopRecording() {
        cleanup()
    }

    function setAudioDataCallback(callback: (audioData: { type: string, data: string, sampleRate: number }) => void) {
        onAudioData = callback
    }

    // Cleanup on component unmount
    onUnmounted(() => {
        cleanup()
    })

    return {
        isRecording,
        error,
        startRecording,
        stopRecording,
        setAudioDataCallback
    }
} 