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
    <div style={{ minHeight: '100vh', padding: '2rem', backgroundColor: '#f5f5f5' }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
        <header style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <h1 style={{ fontSize: '2.5rem', marginBottom: '0.5rem', color: '#333' }}>
            Podcast Generator
          </h1>
          <p style={{ fontSize: '1.2rem', color: '#666' }}>
            Transform your text into engaging podcast conversations
          </p>
        </header>

        <Stepper currentStep={2} steps={STEPS} />
        <div style={{ marginTop: '2rem' }}>
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

