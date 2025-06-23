import { useEffect, useRef, useState } from 'react'
import { AudioPlayer } from '../lib/audioUtils'

export function useAudioPlayer() {
  const audioPlayerRef = useRef<AudioPlayer | null>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [queueLength, setQueueLength] = useState(0)

  useEffect(() => {
    // Initialize audio player
    audioPlayerRef.current = new AudioPlayer()

    // Update state periodically
    const interval = setInterval(() => {
      if (audioPlayerRef.current) {
        setIsPlaying(audioPlayerRef.current.isAudioPlaying)
        setQueueLength(audioPlayerRef.current.queueLength)
      }
    }, 100)

    return () => {
      clearInterval(interval)
      audioPlayerRef.current?.stop()
    }
  }, [])

  const playAudio = async (base64Audio: string, sampleRate: number) => {
    if (audioPlayerRef.current) {
      await audioPlayerRef.current.resume() // Resume context if needed
      await audioPlayerRef.current.queueAudio(base64Audio, sampleRate)
    }
  }

  const stopAudio = () => {
    audioPlayerRef.current?.stop()
    setIsPlaying(false)
    setQueueLength(0)
  }

  return {
    playAudio,
    stopAudio,
    isPlaying,
    queueLength
  }
}