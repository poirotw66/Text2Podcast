import React, { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePodcastContext } from '../contexts/PodcastContext'
import { VOICES, Voice, DEFAULT_VOICES } from '../data/voices'

export const SettingsPage: React.FC = () => {
  const navigate = useNavigate()
  const { voiceSettings, setVoiceSettings } = usePodcastContext()
  const [playingVoice, setPlayingVoice] = useState<string | null>(null)
  const audioRefs = useRef<{ [key: string]: HTMLAudioElement | null }>({})

  const handleVoiceSelect = (speaker: 'Speaker 1' | 'Speaker 2', voiceName: string) => {
    setVoiceSettings({
      ...voiceSettings,
      [speaker]: voiceName
    })
  }

  const handlePlayPreview = (voice: Voice) => {
    // Stop any currently playing audio
    Object.values(audioRefs.current).forEach(audio => {
      if (audio && !audio.paused) {
        audio.pause()
        audio.currentTime = 0
      }
    })

    // Play the selected voice
    const audio = audioRefs.current[voice.name]
    if (audio) {
      audio.play()
      setPlayingVoice(voice.name)
      audio.onended = () => {
        setPlayingVoice(null)
      }
      audio.onerror = () => {
        setPlayingVoice(null)
        console.error(`Failed to play audio for ${voice.name}`)
      }
    }
  }

  const handleStopPreview = () => {
    Object.values(audioRefs.current).forEach(audio => {
      if (audio && !audio.paused) {
        audio.pause()
        audio.currentTime = 0
      }
    })
    setPlayingVoice(null)
  }

  const handleReset = () => {
    setVoiceSettings(DEFAULT_VOICES)
  }

  return (
    <div style={{ minHeight: '100vh', padding: '2rem' }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
        <header style={{ textAlign: 'center', marginBottom: '3rem', animation: 'fadeIn 0.6s ease-out' }}>
          <h1 style={{ 
            fontSize: '3rem', 
            marginBottom: '0.5rem', 
            color: 'white',
            fontWeight: '700',
            textShadow: '0 2px 10px rgba(0,0,0,0.2)',
            letterSpacing: '-0.02em'
          }}>
            ⚙️ Voice Settings
          </h1>
          <p style={{ 
            fontSize: '1.25rem', 
            color: 'rgba(255,255,255,0.9)',
            textShadow: '0 1px 5px rgba(0,0,0,0.2)'
          }}>
            Choose voices for your podcast speakers (both speakers can choose any voice)
          </p>
        </header>

        <div style={{
          backgroundColor: 'rgba(255,255,255,0.95)',
          backdropFilter: 'blur(10px)',
          borderRadius: '1rem',
          padding: '2.5rem',
          boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1), 0 10px 10px -5px rgba(0,0,0,0.04)',
          border: '1px solid rgba(255,255,255,0.2)',
          marginBottom: '2rem',
          animation: 'fadeIn 0.8s ease-out 0.2s both'
        }}>
          {/* Current Settings */}
          <div style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.5rem', marginBottom: '1rem', color: '#333' }}>
              Current Settings
            </h2>
            <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap' }}>
              <div style={{
                padding: '1rem',
                backgroundColor: '#e8f5e9',
                borderRadius: '8px',
                border: '3px solid #4caf50',
                flex: 1,
                minWidth: '200px',
                boxShadow: '0 2px 4px rgba(76, 175, 80, 0.2)'
              }}>
                <div style={{ fontWeight: '600', marginBottom: '0.5rem', color: '#2e7d32', fontSize: '1rem' }}>
                  Speaker 1:
                </div>
                <div style={{ fontSize: '1.2rem', color: '#1b5e20', fontWeight: '500', marginBottom: '0.25rem' }}>
                  {voiceSettings['Speaker 1']}
                </div>
                <div style={{ fontSize: '0.85rem', color: '#388e3c', marginTop: '0.25rem' }}>
                  {VOICES.find(v => v.name === voiceSettings['Speaker 1'])?.gender === 'female' ? '👩 Female' : '👨 Male'}
                </div>
              </div>
              <div style={{
                padding: '1rem',
                backgroundColor: '#f3e5f5',
                borderRadius: '8px',
                border: '3px solid #9c27b0',
                flex: 1,
                minWidth: '200px',
                boxShadow: '0 2px 4px rgba(156, 39, 176, 0.2)'
              }}>
                <div style={{ fontWeight: '600', marginBottom: '0.5rem', color: '#7b1fa2', fontSize: '1rem' }}>
                  Speaker 2:
                </div>
                <div style={{ fontSize: '1.2rem', color: '#6a1b9a', fontWeight: '500', marginBottom: '0.25rem' }}>
                  {voiceSettings['Speaker 2']}
                </div>
                <div style={{ fontSize: '0.85rem', color: '#8e24aa', marginTop: '0.25rem' }}>
                  {VOICES.find(v => v.name === voiceSettings['Speaker 2'])?.gender === 'female' ? '👩 Female' : '👨 Male'}
                </div>
              </div>
            </div>
            <div style={{ marginTop: '1rem', display: 'flex', gap: '1rem' }}>
              <button
                onClick={handleReset}
                style={{
                  padding: '0.5rem 1rem',
                  backgroundColor: '#6c757d',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer'
                }}
              >
                Reset to Default
              </button>
            </div>
          </div>

          {/* Speaker 1 Selection */}
          <div style={{ 
            marginBottom: '2rem',
            padding: '1.5rem',
            backgroundColor: '#e8f5e9',
            borderRadius: '12px',
            border: '3px solid #4caf50'
          }}>
            <h2 style={{ 
              fontSize: '1.3rem', 
              marginBottom: '1rem', 
              color: '#2e7d32',
              fontWeight: '700',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem'
            }}>
              <span style={{ fontSize: '1.5rem' }}>🟢</span>
              Select Speaker 1 Voice
            </h2>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
              gap: '1rem'
            }}>
              {VOICES.map(voice => {
                const isSelected = voiceSettings['Speaker 1'] === voice.name
                const isFemale = voice.gender === 'female'
                
                // Fixed colors: Female = pink, Male = blue (same for all speakers)
                const femaleColors = {
                  border: isSelected ? '#c2185b' : '#f48fb1',
                  background: isSelected ? '#f8bbd0' : '#fce4ec',
                  text: '#880e4f',
                  textLight: '#ad1457'
                }
                const maleColors = {
                  border: isSelected ? '#1976d2' : '#90caf9',
                  background: isSelected ? '#bbdefb' : '#e3f2fd',
                  text: '#0d47a1',
                  textLight: '#1565c0'
                }
                const colors = isFemale ? femaleColors : maleColors
                
                return (
                <div
                  key={voice.name}
                  style={{
                    padding: '1rem',
                    border: `3px solid ${colors.border}`,
                    borderRadius: '8px',
                    backgroundColor: colors.background,
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    boxShadow: isSelected ? `0 4px 8px rgba(${isFemale ? '194, 24, 91' : '25, 118, 210'}, 0.3)` : '0 2px 4px rgba(0,0,0,0.1)'
                  }}
                  onClick={() => handleVoiceSelect('Speaker 1', voice.name)}
                >
                  <div style={{ fontWeight: '600', marginBottom: '0.5rem', color: colors.text }}>
                    {voice.name}
                  </div>
                  <div style={{ fontSize: '0.85rem', color: colors.textLight, marginBottom: '0.5rem' }}>
                    {voice.gender === 'male' ? '👨 Male' : '👩 Female'}
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      if (playingVoice === voice.name) {
                        handleStopPreview()
                      } else {
                        handlePlayPreview(voice)
                      }
                    }}
                    style={{
                      width: '100%',
                      padding: '0.5rem',
                      backgroundColor: playingVoice === voice.name ? '#dc3545' : (isFemale ? '#c2185b' : '#1976d2'),
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      fontSize: '0.9rem',
                      fontWeight: '500'
                    }}
                  >
                    {playingVoice === voice.name ? '⏹️ Stop' : '▶️ Preview'}
                  </button>
                  <audio
                    ref={(el) => {
                      audioRefs.current[voice.name] = el
                    }}
                    src={`/voice/${voice.filename}`}
                    preload="metadata"
                    style={{ display: 'none' }}
                  />
                </div>
                )
              })}
            </div>
          </div>

          {/* Speaker 2 Selection */}
          <div style={{ 
            marginBottom: '2rem',
            padding: '1.5rem',
            backgroundColor: '#f3e5f5',
            borderRadius: '12px',
            border: '3px solid #9c27b0'
          }}>
            <h2 style={{ 
              fontSize: '1.3rem', 
              marginBottom: '1rem', 
              color: '#7b1fa2',
              fontWeight: '700',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem'
            }}>
              <span style={{ fontSize: '1.5rem' }}>🟣</span>
              Select Speaker 2 Voice
            </h2>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
              gap: '1rem'
            }}>
              {VOICES.map(voice => {
                const isSelected = voiceSettings['Speaker 2'] === voice.name
                const isFemale = voice.gender === 'female'
                
                // Fixed colors: Female = pink, Male = blue (same for all speakers)
                const femaleColors = {
                  border: isSelected ? '#c2185b' : '#f48fb1',
                  background: isSelected ? '#f8bbd0' : '#fce4ec',
                  text: '#880e4f',
                  textLight: '#ad1457'
                }
                const maleColors = {
                  border: isSelected ? '#1976d2' : '#90caf9',
                  background: isSelected ? '#bbdefb' : '#e3f2fd',
                  text: '#0d47a1',
                  textLight: '#1565c0'
                }
                const colors = isFemale ? femaleColors : maleColors
                
                return (
                <div
                  key={voice.name}
                  style={{
                    padding: '1rem',
                    border: `3px solid ${colors.border}`,
                    borderRadius: '8px',
                    backgroundColor: colors.background,
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    boxShadow: isSelected ? `0 4px 8px rgba(${isFemale ? '194, 24, 91' : '245, 124, 0'}, 0.3)` : '0 2px 4px rgba(0,0,0,0.1)'
                  }}
                  onClick={() => handleVoiceSelect('Speaker 2', voice.name)}
                >
                  <div style={{ fontWeight: '600', marginBottom: '0.5rem', color: colors.text }}>
                    {voice.name}
                  </div>
                  <div style={{ fontSize: '0.85rem', color: colors.textLight, marginBottom: '0.5rem' }}>
                    {voice.gender === 'male' ? '👨 Male' : '👩 Female'}
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      if (playingVoice === voice.name) {
                        handleStopPreview()
                      } else {
                        handlePlayPreview(voice)
                      }
                    }}
                    style={{
                      width: '100%',
                      padding: '0.5rem',
                      backgroundColor: playingVoice === voice.name ? '#dc3545' : (isFemale ? '#c2185b' : '#1976d2'),
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      fontSize: '0.9rem',
                      fontWeight: '500'
                    }}
                  >
                    {playingVoice === voice.name ? '⏹️ Stop' : '▶️ Preview'}
                  </button>
                  <audio
                    ref={(el) => {
                      audioRefs.current[voice.name] = el
                    }}
                    src={`/voice/${voice.filename}`}
                    preload="metadata"
                    style={{ display: 'none' }}
                  />
                </div>
                )
              })}
            </div>
          </div>

          {/* Navigation */}
          <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center' }}>
            <button
              onClick={() => navigate('/')}
              style={{
                padding: '0.875rem 2rem',
                backgroundColor: '#6366f1',
                color: 'white',
                border: 'none',
                borderRadius: '0.5rem',
                fontSize: '1rem',
                fontWeight: '600',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.5rem'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = '#4f46e5'
                e.currentTarget.style.transform = 'translateY(-2px)'
                e.currentTarget.style.boxShadow = '0 10px 15px -3px rgba(99,102,241,0.3)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = '#6366f1'
                e.currentTarget.style.transform = 'translateY(0)'
                e.currentTarget.style.boxShadow = 'none'
              }}
            >
              <span>←</span>
              Back to Home
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

