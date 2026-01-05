import React from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Stepper } from '../components/Stepper'
import { Step1Upload } from '../components/Step1Upload'
import { usePodcastContext } from '../contexts/PodcastContext'
import { podcastApi } from '../services/api'

const STEPS = [
  'Upload Content',
  'Review & Edit',
  'Confirm Script',
  'Generate & Download'
]

export const Step1Page: React.FC = () => {
  const navigate = useNavigate()
  const { setTaskId, setInitialTranscript } = usePodcastContext()

  const handleStep1Success = async (newTaskId: string) => {
    setTaskId(newTaskId)
    try {
      const response = await podcastApi.step1GenerateInitialTranscript(newTaskId)
      setInitialTranscript(response.initial_transcript)
      navigate(`/edit/${newTaskId}`)
    } catch (error: any) {
      console.error('Failed to generate initial transcript:', error)
      alert(error.response?.data?.detail || 'Failed to generate initial transcript')
    }
  }

  return (
    <div style={{ minHeight: '100vh', padding: '2rem', backgroundColor: '#f5f5f5' }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
        <header style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <div style={{ flex: 1 }}></div>
            <div style={{ flex: 1 }}>
              <h1 style={{ fontSize: '2.5rem', marginBottom: '0.5rem', color: '#333' }}>
                Podcast Generator
              </h1>
              <p style={{ fontSize: '1.2rem', color: '#666' }}>
                Transform your text into engaging podcast conversations
              </p>
            </div>
            <div style={{ flex: 1, display: 'flex', justifyContent: 'flex-end' }}>
              <Link
                to="/settings"
                style={{
                  padding: '0.5rem 1rem',
                  backgroundColor: '#6c757d',
                  color: 'white',
                  textDecoration: 'none',
                  borderRadius: '4px',
                  fontSize: '0.9rem'
                }}
              >
                ⚙️ Settings
              </Link>
            </div>
          </div>
        </header>

        <Stepper currentStep={1} steps={STEPS} />
        <div style={{ marginTop: '2rem' }}>
          <Step1Upload onSuccess={handleStep1Success} />
        </div>
      </div>
    </div>
  )
}

