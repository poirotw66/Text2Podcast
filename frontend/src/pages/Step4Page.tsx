import React, { useEffect, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Stepper } from '../components/Stepper'
import { Step4Result } from '../components/Step4Result'
import { useProgress } from '../hooks/useProgress'
import { usePodcastContext } from '../contexts/PodcastContext'

const STEPS = [
  'Upload Content',
  'Review & Edit',
  'Confirm Script',
  'Generate & Download'
]

export const Step4Page: React.FC = () => {
  const navigate = useNavigate()
  const { taskId: urlTaskId } = useParams<{ taskId: string }>()
  const { taskId, setTaskId, clearAll } = usePodcastContext()

  useEffect(() => {
    if (urlTaskId && urlTaskId !== taskId) {
      setTaskId(urlTaskId)
    }
  }, [urlTaskId, taskId, setTaskId])

  const handleComplete = useCallback(() => {
    console.log('Task completed!')
  }, [])
  
  const handleError = useCallback((error: string) => {
    console.error('Task failed:', error)
  }, [])

  const currentTaskId = urlTaskId || taskId
  const { status } = useProgress({
    taskId: currentTaskId,
    onComplete: handleComplete,
    onError: handleError
  })

  const handleNewPodcast = () => {
    clearAll()
    navigate('/')
  }

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

        <Stepper currentStep={4} steps={STEPS} />
        <div style={{ marginTop: '2rem' }}>
          <Step4Result
            taskId={currentTaskId}
            status={status}
            onNewPodcast={handleNewPodcast}
          />
        </div>
      </div>
    </div>
  )
}

