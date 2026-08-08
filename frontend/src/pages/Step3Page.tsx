import React, { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Stepper } from '../components/Stepper'
import { Step3Confirm } from '../components/Step3Confirm'
import { usePodcastContext } from '../contexts/PodcastContext'
import { podcastApi, getErrorMessage } from '../services/api'
import { MicrophoneIcon } from '../components/icons'

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
    setOptimizedTranscript,
    voiceSettings
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
      await podcastApi.step3GenerateAudio(currentTaskId, optimizedTranscript, voiceSettings)
      navigate(`/result/${currentTaskId}`)
    } catch (error) {
      console.error('Failed to start audio generation:', error)
      alert(getErrorMessage(error, 'Failed to start audio generation'))
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

        <Stepper currentStep={3} steps={STEPS} />
        <div style={{ marginTop: '2rem', animation: 'fadeIn 0.8s ease-out 0.2s both' }}>
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

