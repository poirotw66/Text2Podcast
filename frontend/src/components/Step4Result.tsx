import React from 'react'
import { podcastApi } from '../services/api'
import { ProgressBar } from './ProgressBar'
import { TaskStatus } from '../services/api'

interface Step4ResultProps {
  taskId: string
  status: TaskStatus | null
  onNewPodcast: () => void
}

export const Step4Result: React.FC<Step4ResultProps> = ({ taskId, status, onNewPodcast }) => {
  const handleDownloadAudio = () => {
    const url = podcastApi.getAudioDownloadUrl(taskId)
    const link = document.createElement('a')
    link.href = url
    link.download = `podcast_${taskId}.mp3`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const handleDownloadTranscript = () => {
    const url = podcastApi.getTranscriptDownloadUrl(taskId)
    const link = document.createElement('a')
    link.href = url
    link.download = `transcript_${taskId}.txt`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const isCompleted = status?.status === 'completed'
  const audioUrl = isCompleted && status.audio_file 
    ? podcastApi.getAudioDownloadUrl(taskId)
    : null

  return (
    <div style={{ 
      maxWidth: '900px', 
      margin: '0 auto', 
      padding: '2rem',
      backgroundColor: 'white',
      borderRadius: '8px',
      boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
    }}>
      <h2 style={{ marginBottom: '1rem', textAlign: 'center' }}>Step 4: Your Podcast</h2>

      {!isCompleted && (
        <>
          <ProgressBar status={status} />
          <p style={{ textAlign: 'center', color: '#666', marginTop: '1rem' }}>
            Please wait while we generate your podcast...
          </p>
        </>
      )}

      {isCompleted && (
        <>
          <div style={{
            marginBottom: '2rem',
            padding: '1.5rem',
            backgroundColor: '#f0f8ff',
            borderRadius: '8px',
            border: '2px solid #28a745'
          }}>
            <h3 style={{ marginBottom: '1rem', color: '#28a745', textAlign: 'center' }}>
              ✓ Podcast Generated Successfully!
            </h3>
            
            {audioUrl && (
              <div style={{ marginBottom: '1.5rem' }}>
                <label style={{ 
                  display: 'block', 
                  marginBottom: '0.5rem',
                  fontWeight: '500'
                }}>
                  Listen to your podcast:
                </label>
                <audio 
                  controls 
                  style={{ 
                    width: '100%',
                    marginBottom: '1rem'
                  }}
                >
                  <source src={audioUrl} type="audio/mpeg" />
                  Your browser does not support the audio element.
                </audio>
              </div>
            )}

            <div style={{ 
              display: 'flex', 
              gap: '1rem', 
              justifyContent: 'center',
              flexWrap: 'wrap'
            }}>
              <button
                onClick={handleDownloadAudio}
                style={{
                  padding: '0.75rem 2rem',
                  backgroundColor: '#28a745',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  fontSize: '1rem',
                  fontWeight: '500',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem'
                }}
              >
                <span>📥</span>
                Download Audio (MP3)
              </button>

              <button
                onClick={handleDownloadTranscript}
                style={{
                  padding: '0.75rem 2rem',
                  backgroundColor: '#007bff',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  fontSize: '1rem',
                  fontWeight: '500',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem'
                }}
              >
                <span>📄</span>
                Download Transcript
              </button>
            </div>
          </div>

          <div style={{ textAlign: 'center' }}>
            <button
              onClick={onNewPodcast}
              style={{
                padding: '0.75rem 2rem',
                backgroundColor: '#6c757d',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                fontSize: '1rem',
                fontWeight: '500',
                cursor: 'pointer'
              }}
            >
              Create Another Podcast
            </button>
          </div>
        </>
      )}
    </div>
  )
}

