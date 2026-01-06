import React, { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Stepper } from '../components/Stepper'
import { Step2Edit } from '../components/Step2Edit'
import { usePodcastContext } from '../contexts/PodcastContext'
import { podcastApi } from '../services/api'

const STEPS = [
  'Upload Content',
  'Review & Edit',
  'Confirm Script',
  'Generate & Download'
]

export const Step2Page: React.FC = () => {
  const navigate = useNavigate()
  const { taskId: urlTaskId } = useParams<{ taskId: string }>()
  const { 
    taskId, 
    setTaskId, 
    initialTranscript, 
    setOptimizedTranscript 
  } = usePodcastContext()

  useEffect(() => {
    if (urlTaskId && urlTaskId !== taskId) {
      setTaskId(urlTaskId)
    }
  }, [urlTaskId, taskId, setTaskId])

  const handleStep2Next = async (editedText: string) => {
    const currentTaskId = urlTaskId || taskId
    if (!currentTaskId) return

    try {
      const response = await podcastApi.step2OptimizeTranscript(currentTaskId, editedText)
      setOptimizedTranscript(response.optimized_transcript)
      navigate(`/confirm/${currentTaskId}`)
    } catch (error: any) {
      console.error('Failed to optimize transcript:', error)
      alert(error.response?.data?.detail || 'Failed to optimize transcript')
    }
  }

  const handleStep2Back = () => {
    navigate('/')
  }

  if (!initialTranscript) {
    return (
      <div style={{ textAlign: 'center', padding: '2rem' }}>
        <p>No transcript found. Please start from Step 1.</p>
        <button onClick={() => navigate('/')}>Go to Step 1</button>
      </div>
    )
  }

  const currentTaskId = urlTaskId || taskId
  if (!currentTaskId) {
    return (
      <div style={{ textAlign: 'center', padding: '2rem' }}>
        <p>No task ID found. Please start from Step 1.</p>
        <button onClick={() => navigate('/')}>Go to Step 1</button>
      </div>
    )
  }

  return (
    <div style={{ minHeight: '100vh', padding: '2rem' }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
        <header style={{ textAlign: 'center', marginBottom: '3rem', animation: 'fadeIn 0.6s ease-out' }}>
          <h1 style={{ 
            fontSize: '3rem', 
            marginBottom: '0.5rem', 
            color: 'white',
            fontWeight: '700',
            textShadow: '0 2px 10px rgba(0,0,0,0.2)',
            letterSpacing: '-0.02em'
          }}>
            🎙️ Podcast Generator
          </h1>
          <p style={{ 
            fontSize: '1.25rem', 
            color: 'rgba(255,255,255,0.9)',
            textShadow: '0 1px 5px rgba(0,0,0,0.2)'
          }}>
            Transform your text into engaging podcast conversations
          </p>
        </header>

        <Stepper currentStep={2} steps={STEPS} />
        <div style={{ marginTop: '2rem', animation: 'fadeIn 0.8s ease-out 0.2s both' }}>
          <Step2Edit
            taskId={currentTaskId}
            initialTranscript={initialTranscript}
            onNext={handleStep2Next}
            onBack={handleStep2Back}
          />
        </div>
      </div>
    </div>
  )
}

