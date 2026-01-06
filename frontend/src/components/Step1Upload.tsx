import React, { useState } from 'react'
import { podcastApi } from '../services/api'

interface Step1UploadProps {
  onSuccess: (taskId: string, podcastLengthMode: 'SHORT' | 'MEDIUM' | 'LONG') => void
}

type PodcastLengthMode = 'SHORT' | 'MEDIUM' | 'LONG'

export const Step1Upload: React.FC<Step1UploadProps> = ({ onSuccess }) => {
  const [text, setText] = useState('')
  const [podcastLengthMode, setPodcastLengthMode] = useState<PodcastLengthMode>('MEDIUM')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!text.trim()) {
      setError('Please enter some text content')
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const response = await podcastApi.uploadText(text, podcastLengthMode)
      onSuccess(response.task_id, podcastLengthMode)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to upload text. Please try again.')
      setIsLoading(false)
    }
  }

  return (
    <div style={{ 
      maxWidth: '900px', 
      margin: '0 auto', 
      padding: '2.5rem',
      backgroundColor: 'rgba(255,255,255,0.95)',
      backdropFilter: 'blur(10px)',
      borderRadius: '1rem',
      boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1), 0 10px 10px -5px rgba(0,0,0,0.04)',
      border: '1px solid rgba(255,255,255,0.2)'
    }}>
      <h2 style={{ 
        marginBottom: '0.75rem', 
        textAlign: 'center',
        fontSize: '2rem',
        fontWeight: '700',
        color: '#1f2937',
        letterSpacing: '-0.02em'
      }}>
        Step 1: Upload Your Content
      </h2>
      <p style={{ 
        marginBottom: '2rem', 
        color: '#6b7280', 
        textAlign: 'center',
        fontSize: '1.05rem'
      }}>
        Enter the text content you want to convert into a podcast
      </p>
      
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: '1.5rem' }}>
          <label 
            htmlFor="podcast-length-mode" 
            style={{ 
              display: 'block', 
              marginBottom: '0.75rem',
              fontWeight: '600',
              color: '#374151',
              fontSize: '1rem'
            }}
          >
            Podcast Length Mode:
          </label>
          <select
            id="podcast-length-mode"
            value={podcastLengthMode}
            onChange={(e) => setPodcastLengthMode(e.target.value as PodcastLengthMode)}
            disabled={isLoading}
            style={{
              width: '100%',
              padding: '0.875rem 1rem',
              border: '2px solid #e5e7eb',
              borderRadius: '0.5rem',
              fontSize: '1rem',
              fontFamily: 'inherit',
              backgroundColor: 'white',
              cursor: isLoading ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s ease',
              color: '#1f2937'
            }}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = '#6366f1'
              e.currentTarget.style.boxShadow = '0 0 0 3px rgba(99,102,241,0.1)'
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = '#e5e7eb'
              e.currentTarget.style.boxShadow = 'none'
            }}
          >
            <option value="SHORT">SHORT (約 7 分鐘)</option>
            <option value="MEDIUM">MEDIUM (約 15 分鐘)</option>
            <option value="LONG">LONG (約 30 分鐘)</option>
          </select>
        </div>

        <div style={{ marginBottom: '1.5rem' }}>
          <label 
            htmlFor="text-input" 
            style={{ 
              display: 'block', 
              marginBottom: '0.75rem',
              fontWeight: '600',
              color: '#374151',
              fontSize: '1rem'
            }}
          >
            Text Content:
          </label>
          <textarea
            id="text-input"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste or type your content here..."
            rows={14}
            style={{
              width: '100%',
              padding: '1rem',
              border: '2px solid #e5e7eb',
              borderRadius: '0.5rem',
              fontSize: '1rem',
              fontFamily: 'inherit',
              resize: 'vertical',
              transition: 'all 0.2s ease',
              color: '#1f2937',
              lineHeight: '1.6'
            }}
            disabled={isLoading}
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
          }}>
            <span>⚠️</span>
            <span>{error}</span>
          </div>
        )}

        <button
          type="submit"
          disabled={isLoading || !text.trim()}
          style={{
            padding: '1rem 2rem',
            backgroundColor: isLoading || !text.trim() ? '#d1d5db' : '#6366f1',
            color: 'white',
            border: 'none',
            borderRadius: '0.5rem',
            fontSize: '1.05rem',
            fontWeight: '600',
            cursor: isLoading || !text.trim() ? 'not-allowed' : 'pointer',
            width: '100%',
            transition: 'all 0.2s ease',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.5rem'
          }}
          onMouseEnter={(e) => {
            if (!isLoading && text.trim()) {
              e.currentTarget.style.backgroundColor = '#4f46e5'
              e.currentTarget.style.transform = 'translateY(-2px)'
              e.currentTarget.style.boxShadow = '0 10px 15px -3px rgba(99,102,241,0.3)'
            }
          }}
          onMouseLeave={(e) => {
            if (!isLoading && text.trim()) {
              e.currentTarget.style.backgroundColor = '#6366f1'
              e.currentTarget.style.transform = 'translateY(0)'
              e.currentTarget.style.boxShadow = 'none'
            }
          }}
        >
          {isLoading ? (
            <>
              <span style={{ animation: 'spin 1s linear infinite' }}>⏳</span>
              Processing...
            </>
          ) : (
            <>
              <span>🚀</span>
              Generate Initial Podcast Script
            </>
          )}
        </button>
      </form>
    </div>
  )
}

