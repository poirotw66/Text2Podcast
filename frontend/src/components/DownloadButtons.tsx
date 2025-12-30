import React from 'react'
import { podcastApi } from '../services/api'

interface DownloadButtonsProps {
  taskId: string
  audioFile?: string
  transcriptFile?: string
}

export const DownloadButtons: React.FC<DownloadButtonsProps> = ({
  taskId,
  audioFile,
  transcriptFile
}) => {
  const handleDownload = (url: string, filename: string) => {
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const downloadAudio = () => {
    if (audioFile) {
      handleDownload(
        podcastApi.getAudioDownloadUrl(taskId),
        `podcast_${taskId}.mp3`
      )
    }
  }

  const downloadTranscript = () => {
    if (transcriptFile) {
      handleDownload(
        podcastApi.getTranscriptDownloadUrl(taskId),
        `transcript_${taskId}.txt`
      )
    }
  }

  if (!audioFile && !transcriptFile) {
    return null
  }

  return (
    <div style={{
      maxWidth: '800px',
      margin: '2rem auto',
      padding: '2rem',
      backgroundColor: 'white',
      borderRadius: '8px',
      boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
      textAlign: 'center'
    }}>
      <h3 style={{ marginBottom: '1.5rem' }}>Download Your Podcast</h3>
      
      <div style={{
        display: 'flex',
        gap: '1rem',
        justifyContent: 'center',
        flexWrap: 'wrap'
      }}>
        {audioFile && (
          <button
            onClick={downloadAudio}
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
        )}

        {transcriptFile && (
          <button
            onClick={downloadTranscript}
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
        )}
      </div>
    </div>
  )
}

