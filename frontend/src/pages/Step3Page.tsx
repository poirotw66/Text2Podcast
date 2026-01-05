import React, { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Stepper } from '../components/Stepper'
import { Step3Confirm } from '../components/Step3Confirm'
import { usePodcastContext } from '../contexts/PodcastContext'
import { podcastApi } from '../services/api'

const STEPS = [
  'Upload Content',
  'Review & Edit',
  'Confirm Script',
  'Generate & Download'
]

export const Step3Page: React.FC = () => {
  const navigate = useNavigate()
  const { taskId: urlTaskId } = useParams<{ taskId: string }>()
  const { 
    taskId, 
    setTaskId, 
    optimizedTranscript,
    setOptimizedTranscript
  } = usePodcastContext()

  useEffect(() => {
    if (urlTaskId && urlTaskId !== taskId) {
      setTaskId(urlTaskId)
    }
  }, [urlTaskId, taskId, setTaskId])

  const handleTranscriptChange = (updatedTranscript: Array<[string, string]>) => {
    setOptimizedTranscript(updatedTranscript)
  }

  const handleStep3Confirm = async () => {
    const currentTaskId = urlTaskId || taskId
    if (!currentTaskId) return

    try {
      await podcastApi.step3GenerateAudio(currentTaskId, optimizedTranscript)
      navigate(`/result/${currentTaskId}`)
    } catch (error: any) {
      console.error('Failed to start audio generation:', error)
      alert(error.response?.data?.detail || 'Failed to start audio generation')
    }
  }

  const handleStep3Back = () => {
    const currentTaskId = urlTaskId || taskId
    if (currentTaskId) {
      navigate(`/edit/${currentTaskId}`)
    } else {
      navigate('/')
    }
  }

  if (optimizedTranscript.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '2rem' }}>
        <p>No optimized transcript found. Please complete previous steps.</p>
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

        <Stepper currentStep={3} steps={STEPS} />
        <div style={{ marginTop: '2rem' }}>
          <Step3Confirm
            optimizedTranscript={optimizedTranscript}
            onConfirm={handleStep3Confirm}
            onBack={handleStep3Back}
            onTranscriptChange={handleTranscriptChange}
          />
        </div>
      </div>
    </div>
  )
}

