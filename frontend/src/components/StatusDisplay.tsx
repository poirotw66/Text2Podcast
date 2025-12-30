import React from 'react'
import { TaskStatus } from '../services/api'

interface StatusDisplayProps {
  status: TaskStatus | null
}

export const StatusDisplay: React.FC<StatusDisplayProps> = ({ status }) => {
  if (!status) {
    return null
  }

  return (
    <div style={{
      maxWidth: '800px',
      margin: '1rem auto',
      padding: '1rem',
      backgroundColor: 'white',
      borderRadius: '8px',
      boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <strong>Status:</strong> {status.status}
        </div>
        <div>
          <strong>Progress:</strong> {status.progress}%
        </div>
      </div>
      {status.message && (
        <div style={{ marginTop: '0.5rem', color: '#666' }}>
          {status.message}
        </div>
      )}
    </div>
  )
}

