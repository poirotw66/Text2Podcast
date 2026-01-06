import React, { useEffect, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Stepper } from '../components/Stepper'
import { Step4Result } from '../components/Step4Result'
import { useProgress } from '../hooks/useProgress'
import { usePodcastContext } from '../contexts/PodcastContext'
import { MicrophoneIcon } from '../components/icons'

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
    <div style={{ minHeight: '100vh', padding: '2rem' }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
        <header style={{ textAlign: 'center', marginBottom: '3rem', animation: 'fadeIn 0.6s ease-out' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.75rem' }}>
            <MicrophoneIcon size={48} style={{ color: 'white', filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.2))' }} />
            <h1 style={{ 
              fontSize: '3rem', 
              marginBottom: '0.5rem', 
              color: 'white',
              fontWeight: '700',
              textShadow: '0 2px 10px rgba(0,0,0,0.2)',
              letterSpacing: '-0.02em'
            }}>
              Podcast Generator
            </h1>
          </div>
          <p style={{ 
            fontSize: '1.25rem', 
            color: 'rgba(255,255,255,0.9)',
            textShadow: '0 1px 5px rgba(0,0,0,0.2)'
          }}>
            Transform your text into engaging podcast conversations
          </p>
        </header>

        <Stepper currentStep={4} steps={STEPS} />
        <div style={{ marginTop: '2rem', animation: 'fadeIn 0.8s ease-out 0.2s both' }}>
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

