import React from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Stepper } from '../components/Stepper'
import { Step1Upload } from '../components/Step1Upload'
import { usePodcastContext } from '../contexts/PodcastContext'
import { podcastApi } from '../services/api'
import { MicrophoneIcon, SettingsIcon } from '../components/icons'

const STEPS = [
  'Upload Content',
  'Review & Edit',
  'Confirm Script',
  'Generate & Download'
]

export const Step1Page: React.FC = () => {
  const navigate = useNavigate()
  const { setTaskId, setInitialTranscript } = usePodcastContext()

  const handleStep1Success = async (newTaskId: string, podcastLengthMode: 'SHORT' | 'MEDIUM' | 'LONG') => {
    setTaskId(newTaskId)
    try {
      const response = await podcastApi.step1GenerateInitialTranscript(newTaskId, podcastLengthMode)
      setInitialTranscript(response.initial_transcript)
      navigate(`/edit/${newTaskId}`)
    } catch (error: any) {
      console.error('Failed to generate initial transcript:', error)
      alert(error.response?.data?.detail || 'Failed to generate initial transcript')
    }
  }

  return (
    <div style={{ minHeight: '100vh', padding: '2rem' }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
        <header style={{ textAlign: 'center', marginBottom: '3rem' }} className="fade-in">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <div style={{ flex: 1 }}></div>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
                <MicrophoneIcon size={48} style={{ color: 'white', filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.2))' }} />
                <h1 style={{ 
                  fontSize: '3rem', 
                  marginBottom: 0, 
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
            </div>
            <div style={{ flex: 1, display: 'flex', justifyContent: 'flex-end' }}>
              <Link
                to="/settings"
                style={{
                  padding: '0.625rem 1.25rem',
                  backgroundColor: 'rgba(255,255,255,0.2)',
                  backdropFilter: 'blur(10px)',
                  color: 'white',
                  textDecoration: 'none',
                  borderRadius: '0.5rem',
                  fontSize: '0.9rem',
                  fontWeight: '500',
                  border: '1px solid rgba(255,255,255,0.3)',
                  transition: 'all 0.2s ease',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  cursor: 'pointer'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.3)'
                  e.currentTarget.style.transform = 'translateY(-2px)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.2)'
                  e.currentTarget.style.transform = 'translateY(0)'
                }}
              >
                <SettingsIcon size={18} />
                Settings
              </Link>
            </div>
          </div>
        </header>

        <Stepper currentStep={1} steps={STEPS} />
        <div style={{ marginTop: '2rem' }} className="fade-in">
          <Step1Upload onSuccess={handleStep1Success} />
        </div>
      </div>
    </div>
  )
}

