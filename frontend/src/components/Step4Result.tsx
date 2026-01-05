import React, { useState, useEffect } from 'react'
import { podcastApi } from '../services/api'
import { ProgressBar } from './ProgressBar'
import { TaskStatus } from '../services/api'

interface Step4ResultProps {
  taskId: string
  status: TaskStatus | null
  onNewPodcast: () => void
}

export const Step4Result: React.FC<Step4ResultProps> = ({ taskId, status, onNewPodcast }) => {
  const [transcript, setTranscript] = useState<Array<[string, string]>>([])
  const [loadingTranscript, setLoadingTranscript] = useState(false)
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
  // Always try to construct audio URL when completed, even if status.audio_file is not set
  const audioUrl = isCompleted ? podcastApi.getAudioDownloadUrl(taskId) : null

  useEffect(() => {
    if (isCompleted && transcript.length === 0 && !loadingTranscript) {
      setLoadingTranscript(true)
      podcastApi.getTranscript(taskId)
        .then((data) => {
          setTranscript(data.transcript)
        })
        .catch((error) => {
          console.error('Failed to load transcript:', error)
        })
        .finally(() => {
          setLoadingTranscript(false)
        })
    }
  }, [isCompleted, taskId, transcript.length, loadingTranscript])

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
            
            {/* Audio Player - Always show when completed */}
            <div style={{ marginBottom: '2rem' }}>
              <label style={{ 
                display: 'block', 
                marginBottom: '0.5rem',
                fontWeight: '500',
                fontSize: '1.1rem'
              }}>
                🎧 Listen to your podcast:
              </label>
              {audioUrl ? (
                <audio 
                  controls 
                  style={{ 
                    width: '100%',
                    marginBottom: '1rem'
                  }}
                  onError={(e) => {
                    console.error('Audio load error:', e)
                    const target = e.target as HTMLAudioElement
                    if (target) {
                      target.style.display = 'none'
                    }
                  }}
                >
                  <source src={audioUrl} type="audio/mpeg" />
                  Your browser does not support the audio element.
                </audio>
              ) : (
                <div style={{ 
                  padding: '1rem', 
                  backgroundColor: '#fff3cd', 
                  border: '1px solid #ffc107',
                  borderRadius: '4px',
                  color: '#856404'
                }}>
                  Audio file is being prepared. Please try refreshing the page in a moment.
                </div>
              )}
            </div>

            {/* Transcript Display */}
            {transcript.length > 0 && (
              <div style={{ marginBottom: '2rem' }}>
                <h3 style={{ 
                  marginBottom: '1rem', 
                  fontSize: '1.2rem',
                  fontWeight: '600',
                  color: '#333'
                }}>
                  📝 Podcast Script:
                </h3>
                <div style={{
                  maxHeight: '600px',
                  overflowY: 'auto',
                  border: '1px solid #ddd',
                  borderRadius: '8px',
                  padding: '1rem',
                  backgroundColor: '#f9f9f9'
                }}>
                  {transcript.map(([speaker, text], index) => {
                    // Check if speaker is Speaker 1 or 講者 1 (support both English and Chinese)
                    const isSpeaker1 = speaker.includes('Speaker 1') || speaker.includes('講者 1') || speaker.includes('1')
                    const isSpeaker2 = speaker.includes('Speaker 2') || speaker.includes('講者 2') || speaker.includes('2')
                    
                    // More distinct colors for better differentiation
                    const speaker1Style = {
                      backgroundColor: '#e1f5fe', // Light blue background
                      borderLeft: '4px solid #0277bd', // Dark blue border
                      borderColor: '#0277bd'
                    }
                    
                    const speaker2Style = {
                      backgroundColor: '#fff3e0', // Light orange/amber background
                      borderLeft: '4px solid #ef6c00', // Dark orange border
                      borderColor: '#ef6c00'
                    }
                    
                    const currentStyle = isSpeaker1 ? speaker1Style : (isSpeaker2 ? speaker2Style : {
                      backgroundColor: '#f5f5f5',
                      borderLeft: '4px solid #757575',
                      borderColor: '#757575'
                    })
                    
                    const titleColor = isSpeaker1 ? '#01579b' : (isSpeaker2 ? '#e65100' : '#424242')
                    
                    return (
                      <div 
                        key={index}
                        style={{
                          marginBottom: '1rem',
                          padding: '0.75rem',
                          backgroundColor: currentStyle.backgroundColor,
                          borderRadius: '4px',
                          borderLeft: currentStyle.borderLeft,
                          border: `1px solid ${currentStyle.borderColor}`,
                          boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
                        }}
                      >
                        <div style={{
                          fontWeight: '600',
                          marginBottom: '0.25rem',
                          color: titleColor,
                          fontSize: '1rem'
                        }}>
                          {speaker}:
                        </div>
                        <div style={{ color: '#212121', lineHeight: '1.6', fontSize: '0.95rem' }}>
                          {text}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {loadingTranscript && (
              <div style={{ textAlign: 'center', marginBottom: '2rem', color: '#666' }}>
                Loading transcript...
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

