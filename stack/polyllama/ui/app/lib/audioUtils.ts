/**
 * Audio utilities for playing TTS audio in the browser
 */

export class AudioPlayer {
  private audioContext: AudioContext | null = null
  private audioQueue: { buffer: ArrayBuffer; sampleRate: number }[] = []
  private isPlaying = false
  private currentSource: AudioBufferSourceNode | null = null

  constructor() {
    if (typeof window !== 'undefined') {
      const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
      this.audioContext = new AudioContextClass()
    }
  }

  /**
   * Convert base64 WAV to ArrayBuffer
   */
  private base64ToArrayBuffer(base64: string): ArrayBuffer {
    const binaryString = atob(base64)
    const bytes = new Uint8Array(binaryString.length)
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i)
    }
    return bytes.buffer
  }

  /**
   * Decode WAV data to audio buffer
   */
  private async decodeWAV(arrayBuffer: ArrayBuffer): Promise<AudioBuffer> {
    if (!this.audioContext) throw new Error('AudioContext not initialized')
    return await this.audioContext.decodeAudioData(arrayBuffer)
  }

  /**
   * Queue audio for playback
   */
  async queueAudio(base64Audio: string, sampleRate: number) {
    const arrayBuffer = this.base64ToArrayBuffer(base64Audio)
    this.audioQueue.push({ buffer: arrayBuffer, sampleRate })
    
    // Start playing if not already playing
    if (!this.isPlaying) {
      this.playNext()
    }
  }

  /**
   * Play the next audio in queue
   */
  private async playNext() {
    if (!this.audioContext || this.audioQueue.length === 0) {
      this.isPlaying = false
      return
    }

    this.isPlaying = true
    const { buffer } = this.audioQueue.shift()!

    try {
      const audioBuffer = await this.decodeWAV(buffer)
      
      // Create and connect audio source
      this.currentSource = this.audioContext.createBufferSource()
      this.currentSource.buffer = audioBuffer
      this.currentSource.connect(this.audioContext.destination)
      
      // Play audio
      this.currentSource.start(0)
      
      // When finished, play next
      this.currentSource.onended = () => {
        this.currentSource = null
        this.playNext()
      }
    } catch (error) {
      console.error('Error playing audio:', error)
      // Continue with next audio even on error
      this.playNext()
    }
  }

  /**
   * Stop all audio playback
   */
  stop() {
    if (this.currentSource) {
      this.currentSource.stop()
      this.currentSource = null
    }
    this.audioQueue = []
    this.isPlaying = false
  }

  /**
   * Resume audio context if suspended (needed for some browsers)
   */
  async resume() {
    if (this.audioContext?.state === 'suspended') {
      await this.audioContext.resume()
    }
  }

  /**
   * Get the current playback state
   */
  get isAudioPlaying() {
    return this.isPlaying
  }

  /**
   * Get the number of audio chunks in queue
   */
  get queueLength() {
    return this.audioQueue.length
  }
}