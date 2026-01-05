import React, { createContext, useContext, useState, useEffect } from 'react'
import { DEFAULT_VOICES } from '../data/voices'

interface VoiceSettings {
  'Speaker 1': string
  'Speaker 2': string
}

interface PodcastContextType {
  taskId: string | null
  setTaskId: (id: string | null) => void
  initialTranscript: string
  setInitialTranscript: (text: string) => void
  editedTranscript: string
  setEditedTranscript: (text: string) => void
  optimizedTranscript: Array<[string, string]>
  setOptimizedTranscript: (transcript: Array<[string, string]>) => void
  voiceSettings: VoiceSettings
  setVoiceSettings: (settings: VoiceSettings) => void
  clearAll: () => void
}

const PodcastContext = createContext<PodcastContextType | undefined>(undefined)

export const PodcastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [taskId, setTaskId] = useState<string | null>(null)
  const [initialTranscript, setInitialTranscript] = useState<string>('')
  const [editedTranscript, setEditedTranscript] = useState<string>('')
  const [optimizedTranscript, setOptimizedTranscript] = useState<Array<[string, string]>>([])
  const [voiceSettings, setVoiceSettings] = useState<VoiceSettings>(DEFAULT_VOICES)

  // Load from localStorage on mount
  useEffect(() => {
    const savedTaskId = localStorage.getItem('podcast_taskId')
    const savedInitial = localStorage.getItem('podcast_initialTranscript')
    const savedEdited = localStorage.getItem('podcast_editedTranscript')
    const savedOptimized = localStorage.getItem('podcast_optimizedTranscript')
    const savedVoices = localStorage.getItem('podcast_voiceSettings')

    if (savedTaskId) setTaskId(savedTaskId)
    if (savedInitial) setInitialTranscript(savedInitial)
    if (savedEdited) setEditedTranscript(savedEdited)
    if (savedOptimized) {
      try {
        setOptimizedTranscript(JSON.parse(savedOptimized))
      } catch (e) {
        console.error('Failed to parse optimized transcript:', e)
      }
    }
    if (savedVoices) {
      try {
        setVoiceSettings(JSON.parse(savedVoices))
      } catch (e) {
        console.error('Failed to parse voice settings:', e)
      }
    }
  }, [])

  // Save to localStorage whenever state changes
  useEffect(() => {
    if (taskId) {
      localStorage.setItem('podcast_taskId', taskId)
    } else {
      localStorage.removeItem('podcast_taskId')
    }
  }, [taskId])

  useEffect(() => {
    if (initialTranscript) {
      localStorage.setItem('podcast_initialTranscript', initialTranscript)
    } else {
      localStorage.removeItem('podcast_initialTranscript')
    }
  }, [initialTranscript])

  useEffect(() => {
    if (editedTranscript) {
      localStorage.setItem('podcast_editedTranscript', editedTranscript)
    } else {
      localStorage.removeItem('podcast_editedTranscript')
    }
  }, [editedTranscript])

  useEffect(() => {
    if (optimizedTranscript.length > 0) {
      localStorage.setItem('podcast_optimizedTranscript', JSON.stringify(optimizedTranscript))
    } else {
      localStorage.removeItem('podcast_optimizedTranscript')
    }
  }, [optimizedTranscript])

  useEffect(() => {
    localStorage.setItem('podcast_voiceSettings', JSON.stringify(voiceSettings))
  }, [voiceSettings])

  const clearAll = () => {
    setTaskId(null)
    setInitialTranscript('')
    setEditedTranscript('')
    setOptimizedTranscript([])
    localStorage.removeItem('podcast_taskId')
    localStorage.removeItem('podcast_initialTranscript')
    localStorage.removeItem('podcast_editedTranscript')
    localStorage.removeItem('podcast_optimizedTranscript')
    // Note: voiceSettings are preserved when clearing
  }

  return (
    <PodcastContext.Provider
      value={{
        taskId,
        setTaskId,
        initialTranscript,
        setInitialTranscript,
        editedTranscript,
        setEditedTranscript,
        optimizedTranscript,
        setOptimizedTranscript,
        voiceSettings,
        setVoiceSettings,
        clearAll
      }}
    >
      {children}
    </PodcastContext.Provider>
  )
}

export const usePodcastContext = () => {
  const context = useContext(PodcastContext)
  if (!context) {
    throw new Error('usePodcastContext must be used within PodcastProvider')
  }
  return context
}

