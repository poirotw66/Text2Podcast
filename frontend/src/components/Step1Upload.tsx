import React, { useState } from 'react'
import { podcastApi } from '../services/api'

interface Step1UploadProps {
  onSuccess: (taskId: string) => void
}

export const Step1Upload: React.FC<Step1UploadProps> = ({ onSuccess }) => {
  const [text, setText] = useState('')
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
      const response = await podcastApi.uploadText(text)
      onSuccess(response.task_id)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to upload text. Please try again.')
      setIsLoading(false)
    }
  }

  return (
    <div style={{ 
      maxWidth: '800px', 
      margin: '0 auto', 
      padding: '2rem',
      backgroundColor: 'white',
      borderRadius: '8px',
      boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
    }}>
      <h2 style={{ marginBottom: '1rem', textAlign: 'center' }}>Step 1: Upload Your Content</h2>
      <p style={{ marginBottom: '1.5rem', color: '#666', textAlign: 'center' }}>
        Enter the text content you want to convert into a podcast
      </p>
      
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: '1rem' }}>
          <label 
            htmlFor="text-input" 
            style={{ 
              display: 'block', 
              marginBottom: '0.5rem',
              fontWeight: '500'
            }}
          >
            Text Content:
          </label>
          <textarea
            id="text-input"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste or type your content here..."
            rows={12}
            style={{
              width: '100%',
              padding: '0.75rem',
              border: '1px solid #ddd',
              borderRadius: '4px',
              fontSize: '1rem',
              fontFamily: 'inherit',
              resize: 'vertical'
            }}
            disabled={isLoading}
          />
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

        <button
          type="submit"
          disabled={isLoading || !text.trim()}
          style={{
            padding: '0.75rem 2rem',
            backgroundColor: isLoading ? '#ccc' : '#007bff',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            fontSize: '1rem',
            fontWeight: '500',
            cursor: isLoading ? 'not-allowed' : 'pointer',
            width: '100%'
          }}
        >
          {isLoading ? 'Processing...' : 'Generate Initial Podcast Script'}
        </button>
      </form>
    </div>
  )
}

