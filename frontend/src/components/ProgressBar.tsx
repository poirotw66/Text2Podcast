import React from 'react'
import { TaskStatus } from '../services/api'

interface ProgressBarProps {
  status: TaskStatus | null
}

export const ProgressBar: React.FC<ProgressBarProps> = ({ status }) => {
  if (!status) {
    return null
  }

  const getStatusLabel = () => {
    switch (status.status) {
      case 'pending':
        return 'Waiting to start...'
      case 'processing':
      case 'step1':
        return 'Generating initial transcript...'
      case 'step2':
        return 'Optimizing transcript...'
      case 'step3':
        return 'Generating audio files...'
      case 'completed':
        return 'Completed!'
      case 'failed':
        return 'Failed'
      default:
        return status.message || 'Processing...'
    }
  }

  const getStatusColor = () => {
    switch (status.status) {
      case 'completed':
        return '#28a745'
      case 'failed':
        return '#dc3545'
      default:
        return '#007bff'
    }
  }

  return (
    <div style={{
      maxWidth: '800px',
      margin: '2rem auto',
      padding: '2rem',
      backgroundColor: 'white',
      borderRadius: '8px',
      boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
    }}>
      <h3 style={{ marginBottom: '1rem' }}>Generation Progress</h3>
      
      <div style={{ marginBottom: '0.5rem' }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginBottom: '0.5rem'
        }}>
          <span style={{ fontWeight: '500' }}>{getStatusLabel()}</span>
          <span style={{ color: '#666' }}>{status.progress}%</span>
        </div>
        
        <div style={{
          width: '100%',
          height: '24px',
          backgroundColor: '#e9ecef',
          borderRadius: '12px',
          overflow: 'hidden'
        }}>
          <div
            style={{
              width: `${status.progress}%`,
              height: '100%',
              backgroundColor: getStatusColor(),
              transition: 'width 0.3s ease',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'white',
              fontSize: '0.75rem',
              fontWeight: '500'
            }}
          >
            {status.progress}%
          </div>
        </div>
      </div>

      {status.message && (
        <p style={{
          marginTop: '0.5rem',
          color: '#666',
          fontSize: '0.9rem'
        }}>
          {status.message}
        </p>
      )}

      {status.error && (
        <div style={{
          marginTop: '1rem',
          padding: '0.75rem',
          backgroundColor: '#fee',
          color: '#c33',
          borderRadius: '4px',
          border: '1px solid #fcc'
        }}>
          Error: {status.error}
        </div>
      )}
    </div>
  )
}

