import React, { useState, useEffect } from 'react'
import { podcastApi } from '../services/api'

interface Step2EditProps {
  taskId: string
  initialTranscript: string
  onNext: (editedTranscript: string) => void
  onBack: () => void
}

export const Step2Edit: React.FC<Step2EditProps> = ({ 
  taskId, 
  initialTranscript, 
  onNext, 
  onBack 
}) => {
  const [editedText, setEditedText] = useState(initialTranscript)
  const [isRegenerating, setIsRegenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setEditedText(initialTranscript)
  }, [initialTranscript])

  const handleRegenerate = async () => {
    setIsRegenerating(true)
    setError(null)

    try {
      const response = await podcastApi.step1GenerateInitialTranscript(taskId)
      setEditedText(response.initial_transcript)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to regenerate transcript')
    } finally {
      setIsRegenerating(false)
    }
  }

  const handleNext = () => {
    onNext(editedText)
  }

  return (
    <div style={{ 
      maxWidth: '900px', 
      margin: '0 auto', 
      padding: '2rem',
      backgroundColor: 'white',
      borderRadius: '8px',
      boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
    }}>
      <h2 style={{ marginBottom: '1rem', textAlign: 'center' }}>Step 2: Review & Edit Script</h2>
      <p style={{ marginBottom: '1.5rem', color: '#666', textAlign: 'center' }}>
        Review the generated podcast script. You can edit it directly or regenerate if needed.
      </p>

      <div style={{ marginBottom: '1rem', display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
        <button
          onClick={handleRegenerate}
          disabled={isRegenerating}
          style={{
            padding: '0.5rem 1rem',
            backgroundColor: isRegenerating ? '#ccc' : '#6c757d',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            fontSize: '0.9rem',
            cursor: isRegenerating ? 'not-allowed' : 'pointer'
          }}
        >
          {isRegenerating ? 'Regenerating...' : '🔄 Regenerate Script'}
        </button>
      </div>

      {error && (
        <div style={{
          padding: '0.75rem',
          marginBottom: '1rem',
          backgroundColor: '#fee',
          color: '#c33',
          borderRadius: '4px',
          border: '1px solid #fcc'
        }}>
          {error}
        </div>
      )}

      <div style={{ marginBottom: '1.5rem' }}>
        <label 
          htmlFor="edit-text" 
          style={{ 
            display: 'block', 
            marginBottom: '0.5rem',
            fontWeight: '500'
          }}
        >
          Podcast Script (Editable):
        </label>
        <textarea
          id="edit-text"
          value={editedText}
          onChange={(e) => setEditedText(e.target.value)}
          rows={20}
          style={{
            width: '100%',
            padding: '0.75rem',
            border: '1px solid #ddd',
            borderRadius: '4px',
            fontSize: '1rem',
            fontFamily: 'inherit',
            resize: 'vertical',
            lineHeight: '1.6'
          }}
        />
      </div>

      <div style={{ display: 'flex', gap: '1rem', justifyContent: 'space-between' }}>
        <button
          onClick={onBack}
          style={{
            padding: '0.75rem 2rem',
            backgroundColor: '#6c757d',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            fontSize: '1rem',
            fontWeight: '500',
            cursor: 'pointer',
            flex: 1
          }}
        >
          ← Back
        </button>
        <button
          onClick={handleNext}
          disabled={!editedText.trim()}
          style={{
            padding: '0.75rem 2rem',
            backgroundColor: !editedText.trim() ? '#ccc' : '#007bff',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            fontSize: '1rem',
            fontWeight: '500',
            cursor: !editedText.trim() ? 'not-allowed' : 'pointer',
            flex: 1
          }}
        >
          Optimize Script →
        </button>
      </div>
    </div>
  )
}

