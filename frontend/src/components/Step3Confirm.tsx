import React, { useState } from 'react'

interface Step3ConfirmProps {
  optimizedTranscript: Array<[string, string]>
  onConfirm: () => void
  onBack: () => void
}

export const Step3Confirm: React.FC<Step3ConfirmProps> = ({ 
  optimizedTranscript, 
  onConfirm, 
  onBack 
}) => {
  const [isGenerating, setIsGenerating] = useState(false)

  const handleConfirm = async () => {
    setIsGenerating(true)
    onConfirm()
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
      <h2 style={{ marginBottom: '1rem', textAlign: 'center' }}>Step 3: Confirm Final Script</h2>
      <p style={{ marginBottom: '1.5rem', color: '#666', textAlign: 'center' }}>
        Review the optimized podcast script. Click "Generate Podcast" to create the audio.
      </p>

      <div style={{
        maxHeight: '500px',
        overflowY: 'auto',
        border: '1px solid #ddd',
        borderRadius: '4px',
        padding: '1rem',
        marginBottom: '1.5rem',
        backgroundColor: '#f9f9f9'
      }}>
        {optimizedTranscript.map(([speaker, text], index) => (
          <div 
            key={index}
            style={{
              marginBottom: '1rem',
              padding: '0.75rem',
              backgroundColor: speaker === 'Speaker 1' ? '#e3f2fd' : '#f3e5f5',
              borderRadius: '4px',
              borderLeft: `4px solid ${speaker === 'Speaker 1' ? '#2196f3' : '#9c27b0'}`
            }}
          >
            <div style={{
              fontWeight: '600',
              marginBottom: '0.25rem',
              color: speaker === 'Speaker 1' ? '#1976d2' : '#7b1fa2'
            }}>
              {speaker}:
            </div>
            <div style={{ color: '#333', lineHeight: '1.6' }}>
              {text}
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: '1rem', justifyContent: 'space-between' }}>
        <button
          onClick={onBack}
          disabled={isGenerating}
          style={{
            padding: '0.75rem 2rem',
            backgroundColor: isGenerating ? '#ccc' : '#6c757d',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            fontSize: '1rem',
            fontWeight: '500',
            cursor: isGenerating ? 'not-allowed' : 'pointer',
            flex: 1
          }}
        >
          ← Back
        </button>
        <button
          onClick={handleConfirm}
          disabled={isGenerating}
          style={{
            padding: '0.75rem 2rem',
            backgroundColor: isGenerating ? '#ccc' : '#28a745',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            fontSize: '1rem',
            fontWeight: '500',
            cursor: isGenerating ? 'not-allowed' : 'pointer',
            flex: 2
          }}
        >
          {isGenerating ? 'Generating Podcast...' : '🎙️ Generate Podcast'}
        </button>
      </div>
    </div>
  )
}

