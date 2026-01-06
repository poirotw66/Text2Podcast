import React, { useState, useEffect } from 'react'
import { podcastApi } from '../services/api'
import { RefreshIcon, LoaderIcon, ArrowLeftIcon, ArrowRightIcon } from './icons'

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
    <div className="glass-card" style={{ 
      maxWidth: '900px', 
      margin: '0 auto', 
      padding: '2.5rem',
      borderRadius: '1rem'
    }}>
      <h2 style={{ 
        marginBottom: '0.75rem', 
        textAlign: 'center',
        fontSize: '2rem',
        fontWeight: '700',
        color: '#1f2937',
        letterSpacing: '-0.02em'
      }}>
        Step 2: Review & Edit Script
      </h2>
      <p style={{ 
        marginBottom: '2rem', 
        color: '#6b7280', 
        textAlign: 'center',
        fontSize: '1.05rem'
      }}>
        Review the generated podcast script. You can edit it directly or regenerate if needed.
      </p>

      <div style={{ marginBottom: '1.5rem', display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
        <button
          onClick={handleRegenerate}
          disabled={isRegenerating}
          style={{
            padding: '0.625rem 1.25rem',
            backgroundColor: isRegenerating ? '#d1d5db' : '#6b7280',
            color: 'white',
            border: 'none',
            borderRadius: '0.5rem',
            fontSize: '0.95rem',
            fontWeight: '500',
            cursor: isRegenerating ? 'not-allowed' : 'pointer',
            transition: 'all 0.2s ease',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.5rem'
          }}
          onMouseEnter={(e) => {
            if (!isRegenerating) {
              e.currentTarget.style.backgroundColor = '#4b5563'
              e.currentTarget.style.transform = 'translateY(-1px)'
            }
          }}
          onMouseLeave={(e) => {
            if (!isRegenerating) {
              e.currentTarget.style.backgroundColor = '#6b7280'
              e.currentTarget.style.transform = 'translateY(0)'
            }
          }}
        >
          {isRegenerating ? (
            <>
              <LoaderIcon size={18} />
              Regenerating...
            </>
          ) : (
            <>
              <RefreshIcon size={18} />
              Regenerate Script
            </>
          )}
        </button>
      </div>

          {error && (
        <div style={{
          padding: '1rem',
          marginBottom: '1.5rem',
          backgroundColor: '#fef2f2',
          color: '#dc2626',
          borderRadius: '0.5rem',
          border: '2px solid #fecaca',
          fontSize: '0.95rem',
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem'
        }} role="alert">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
          <span>{error}</span>
        </div>
      )}

      <div style={{ marginBottom: '2rem' }}>
        <label 
          htmlFor="edit-text" 
          style={{ 
            display: 'block', 
            marginBottom: '0.75rem',
            fontWeight: '600',
            color: '#374151',
            fontSize: '1rem'
          }}
        >
          Podcast Script (Editable):
        </label>
        <textarea
          id="edit-text"
          value={editedText}
          onChange={(e) => setEditedText(e.target.value)}
          rows={22}
          style={{
            width: '100%',
            padding: '1rem',
            border: '2px solid #e5e7eb',
            borderRadius: '0.5rem',
            fontSize: '1rem',
            fontFamily: 'inherit',
            resize: 'vertical',
            lineHeight: '1.6',
            transition: 'all 0.2s ease',
            color: '#1f2937',
            backgroundColor: 'white'
          }}
          onFocus={(e) => {
            e.currentTarget.style.borderColor = '#6366f1'
            e.currentTarget.style.boxShadow = '0 0 0 3px rgba(99,102,241,0.1)'
          }}
          onBlur={(e) => {
            e.currentTarget.style.borderColor = '#e5e7eb'
            e.currentTarget.style.boxShadow = 'none'
          }}
        />
      </div>

      <div style={{ display: 'flex', gap: '1rem', justifyContent: 'space-between' }}>
        <button
          onClick={onBack}
          style={{
            padding: '0.875rem 2rem',
            backgroundColor: '#6b7280',
            color: 'white',
            border: 'none',
            borderRadius: '0.5rem',
            fontSize: '1rem',
            fontWeight: '600',
            cursor: 'pointer',
            flex: 1,
            transition: 'all 0.2s ease',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.5rem'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = '#4b5563'
            e.currentTarget.style.transform = 'translateY(-2px)'
            e.currentTarget.style.boxShadow = '0 4px 6px rgba(0,0,0,0.1)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = '#6b7280'
            e.currentTarget.style.transform = 'translateY(0)'
            e.currentTarget.style.boxShadow = 'none'
          }}
        >
          <ArrowLeftIcon size={18} />
          Back
        </button>
        <button
          onClick={handleNext}
          disabled={!editedText.trim()}
          style={{
            padding: '0.875rem 2rem',
            backgroundColor: !editedText.trim() ? '#d1d5db' : '#6366f1',
            color: 'white',
            border: 'none',
            borderRadius: '0.5rem',
            fontSize: '1rem',
            fontWeight: '600',
            cursor: !editedText.trim() ? 'not-allowed' : 'pointer',
            flex: 1,
            transition: 'all 0.2s ease',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.5rem'
          }}
          onMouseEnter={(e) => {
            if (editedText.trim()) {
              e.currentTarget.style.backgroundColor = '#4f46e5'
              e.currentTarget.style.transform = 'translateY(-2px)'
              e.currentTarget.style.boxShadow = '0 10px 15px -3px rgba(99,102,241,0.3)'
            }
          }}
          onMouseLeave={(e) => {
            if (editedText.trim()) {
              e.currentTarget.style.backgroundColor = '#6366f1'
              e.currentTarget.style.transform = 'translateY(0)'
              e.currentTarget.style.boxShadow = 'none'
            }
          }}
        >
          Optimize Script
          <ArrowRightIcon size={18} />
        </button>
      </div>
    </div>
  )
}

