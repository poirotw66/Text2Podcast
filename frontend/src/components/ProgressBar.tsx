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
      padding: '2.5rem',
      backgroundColor: 'rgba(255,255,255,0.95)',
      backdropFilter: 'blur(10px)',
      borderRadius: '1rem',
      boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1), 0 10px 10px -5px rgba(0,0,0,0.04)',
      border: '1px solid rgba(255,255,255,0.2)'
    }}>
      <h3 style={{ 
        marginBottom: '1.5rem',
        fontSize: '1.5rem',
        fontWeight: '700',
        color: '#1f2937',
        textAlign: 'center'
      }}>
        Generation Progress
      </h3>
      
      <div style={{ marginBottom: '1rem' }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginBottom: '0.75rem',
          alignItems: 'center'
        }}>
          <span style={{ 
            fontWeight: '600',
            color: '#374151',
            fontSize: '1.05rem'
          }}>
            {getStatusLabel()}
          </span>
          <span style={{ 
            color: '#6b7280',
            fontWeight: '600',
            fontSize: '1.05rem'
          }}>
            {status.progress}%
          </span>
        </div>
        
        <div style={{
          width: '100%',
          height: '32px',
          backgroundColor: '#e5e7eb',
          borderRadius: '16px',
          overflow: 'hidden',
          boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.06)'
        }}>
          <div
            style={{
              width: `${status.progress}%`,
              height: '100%',
              background: `linear-gradient(90deg, ${getStatusColor()} 0%, ${getStatusColor()}dd 100%)`,
              transition: 'width 0.3s ease',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'white',
              fontSize: '0.875rem',
              fontWeight: '600',
              boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
              position: 'relative',
              overflow: 'hidden'
            }}
          >
            {status.progress > 5 && (
              <span>{status.progress}%</span>
            )}
            {status.progress < 100 && status.status !== 'failed' && (
              <div style={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent)',
                animation: 'pulse 2s ease-in-out infinite'
              }} />
            )}
          </div>
        </div>
      </div>

      {status.message && (
        <p style={{
          marginTop: '1rem',
          color: '#6b7280',
          fontSize: '0.95rem',
          textAlign: 'center',
          padding: '0.75rem',
          backgroundColor: '#f9fafb',
          borderRadius: '0.5rem'
        }}>
          {status.message}
        </p>
      )}

      {status.error && (
        <div style={{
          marginTop: '1rem',
          padding: '1rem',
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
          <span><strong>Error:</strong> {status.error}</span>
        </div>
      )}
    </div>
  )
}

