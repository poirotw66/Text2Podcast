import React, { useState, useCallback } from 'react'
import { Stepper } from './components/Stepper'
import { Step1Upload } from './components/Step1Upload'
import { Step2Edit } from './components/Step2Edit'
import { Step3Confirm } from './components/Step3Confirm'
import { Step4Result } from './components/Step4Result'
import { useProgress } from './hooks/useProgress'
import { podcastApi } from './services/api'

const STEPS = [
  'Upload Content',
  'Review & Edit',
  'Confirm Script',
  'Generate & Download'
]

function App() {
  const [currentStep, setCurrentStep] = useState(1)
  const [taskId, setTaskId] = useState<string | null>(null)
  const [initialTranscript, setInitialTranscript] = useState<string>('')
  const [editedTranscript, setEditedTranscript] = useState<string>('')
  const [optimizedTranscript, setOptimizedTranscript] = useState<Array<[string, string]>>([])

  const handleComplete = useCallback(() => {
    console.log('Task completed!')
  }, [])
  
  const handleError = useCallback((error: string) => {
    console.error('Task failed:', error)
  }, [])

  // Only track progress in step 4 (audio generation)
  const { status } = useProgress({
    taskId: currentStep === 4 ? taskId : null,
    onComplete: handleComplete,
    onError: handleError
  })

  // Step 1: Upload text and generate initial transcript
  const handleStep1Success = async (newTaskId: string) => {
    setTaskId(newTaskId)
    try {
      const response = await podcastApi.step1GenerateInitialTranscript(newTaskId)
      setInitialTranscript(response.initial_transcript)
      setCurrentStep(2)
    } catch (error: any) {
      console.error('Failed to generate initial transcript:', error)
      alert(error.response?.data?.detail || 'Failed to generate initial transcript')
    }
  }

  // Step 2: Edit transcript and optimize
  const handleStep2Next = async (editedText: string) => {
    setEditedTranscript(editedText)
    if (!taskId) return

    try {
      const response = await podcastApi.step2OptimizeTranscript(taskId, editedText)
      setOptimizedTranscript(response.optimized_transcript)
      setCurrentStep(3)
    } catch (error: any) {
      console.error('Failed to optimize transcript:', error)
      alert(error.response?.data?.detail || 'Failed to optimize transcript')
    }
  }

  const handleStep2Back = () => {
    setCurrentStep(1)
  }

  // Step 3: Confirm and generate audio
  const handleStep3Confirm = async () => {
    if (!taskId) return

    try {
      await podcastApi.step3GenerateAudio(taskId, optimizedTranscript)
      setCurrentStep(4)
    } catch (error: any) {
      console.error('Failed to start audio generation:', error)
      alert(error.response?.data?.detail || 'Failed to start audio generation')
    }
  }

  const handleStep3Back = () => {
    setCurrentStep(2)
  }

  // Step 4: Reset for new podcast
  const handleNewPodcast = () => {
    setCurrentStep(1)
    setTaskId(null)
    setInitialTranscript('')
    setEditedTranscript('')
    setOptimizedTranscript([])
  }

  return (
    <div style={{ minHeight: '100vh', padding: '2rem', backgroundColor: '#f5f5f5' }}>
      <div style={{
        maxWidth: '1200px',
        margin: '0 auto'
      }}>
        <header style={{
          textAlign: 'center',
          marginBottom: '2rem'
        }}>
          <h1 style={{
            fontSize: '2.5rem',
            marginBottom: '0.5rem',
            color: '#333'
          }}>
            Podcast Generator
          </h1>
          <p style={{
            fontSize: '1.2rem',
            color: '#666'
          }}>
            Transform your text into engaging podcast conversations
          </p>
        </header>

        <Stepper currentStep={currentStep} steps={STEPS} />

        <div style={{ marginTop: '2rem' }}>
          {currentStep === 1 && (
            <Step1Upload onSuccess={handleStep1Success} />
          )}

          {currentStep === 2 && taskId && initialTranscript && (
            <Step2Edit
              taskId={taskId}
              initialTranscript={initialTranscript}
              onNext={handleStep2Next}
              onBack={handleStep2Back}
            />
          )}

          {currentStep === 3 && optimizedTranscript.length > 0 && (
            <Step3Confirm
              optimizedTranscript={optimizedTranscript}
              onConfirm={handleStep3Confirm}
              onBack={handleStep3Back}
            />
          )}

          {currentStep === 4 && taskId && (
            <Step4Result
              taskId={taskId}
              status={status}
              onNewPodcast={handleNewPodcast}
            />
          )}
        </div>
      </div>
    </div>
  )
}

export default App
