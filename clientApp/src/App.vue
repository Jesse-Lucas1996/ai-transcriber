<template>
  <div class="app-container">
    <header class="app-header">
      <h1 class="app-title">AI Transcriber</h1>
      <p class="app-subtitle">Real-time speech transcription with speaker diarization</p>
    </header>
    <main class="app-main">
      <RecordingInterface />
    </main>
    <footer class="app-footer">
      <p>Powered by AI • Built with Vue 3</p>
    </footer>
  </div>
</template>

<script setup lang="ts">
import RecordingInterface from './components/RecordingInterface.vue'
</script>
