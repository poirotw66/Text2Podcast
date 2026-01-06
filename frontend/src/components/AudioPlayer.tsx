import React, { useRef, useState, useEffect } from 'react'

interface AudioPlayerProps {
  src: string
  onError?: (error: Event) => void
}

export const AudioPlayer: React.FC<AudioPlayerProps> = ({ src, onError }) => {
  const audioRef = useRef<HTMLAudioElement>(null)
  const progressRef = useRef<HTMLDivElement>(null)
  const isDraggingRef = useRef(false)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [isDragging, setIsDragging] = useState(false)

  // Update ref when state changes
  useEffect(() => {
    isDraggingRef.current = isDragging
  }, [isDragging])

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return

    const updateTime = () => {
      if (!isDraggingRef.current) {
        setCurrentTime(audio.currentTime)
      }
    }

    const updateDuration = () => {
      setDuration(audio.duration)
    }

    const handleEnded = () => {
      setIsPlaying(false)
      setCurrentTime(0)
    }

    const handleError = (e: Event) => {
      if (onError) {
        onError(e)
      }
    }

    audio.addEventListener('timeupdate', updateTime)
    audio.addEventListener('loadedmetadata', updateDuration)
    audio.addEventListener('ended', handleEnded)
    audio.addEventListener('error', handleError)

    return () => {
      audio.removeEventListener('timeupdate', updateTime)
      audio.removeEventListener('loadedmetadata', updateDuration)
      audio.removeEventListener('ended', handleEnded)
      audio.removeEventListener('error', handleError)
    }
  }, [onError])

  const togglePlay = () => {
    const audio = audioRef.current
    if (!audio) return

    if (isPlaying) {
      audio.pause()
    } else {
      audio.play()
    }
    setIsPlaying(!isPlaying)
  }

  const formatTime = (seconds: number): string => {
    if (isNaN(seconds) || !isFinite(seconds)) return '0:00'
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const getProgressPercentage = (): number => {
    if (!duration || duration === 0) return 0
    return (currentTime / duration) * 100
  }

  const calculateTimeFromEvent = (clientX: number): number => {
    const audio = audioRef.current
    const progressBar = progressRef.current
    if (!audio || !progressBar || !duration) return 0

    const rect = progressBar.getBoundingClientRect()
    const clickX = clientX - rect.left
    const percentage = Math.max(0, Math.min(1, clickX / rect.width))
    return percentage * duration
  }

  const handleProgressClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (isDraggingRef.current) return // Don't handle click if we're dragging
    const newTime = calculateTimeFromEvent(e.clientX)
    const audio = audioRef.current
    if (audio) {
      audio.currentTime = newTime
      setCurrentTime(newTime)
    }
  }

  const handleProgressMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(true)
    const newTime = calculateTimeFromEvent(e.clientX)
    const audio = audioRef.current
    if (audio) {
      audio.currentTime = newTime
      setCurrentTime(newTime)
    }
  }

  // Global mouse move handler for dragging
  useEffect(() => {
    if (!isDragging) return

    const handleGlobalMouseMove = (e: MouseEvent) => {
      const newTime = calculateTimeFromEvent(e.clientX)
      const audio = audioRef.current
      if (audio) {
        audio.currentTime = newTime
        setCurrentTime(newTime)
      }
    }

    const handleGlobalMouseUp = () => {
      setIsDragging(false)
    }

    document.addEventListener('mousemove', handleGlobalMouseMove)
    document.addEventListener('mouseup', handleGlobalMouseUp)

    return () => {
      document.removeEventListener('mousemove', handleGlobalMouseMove)
      document.removeEventListener('mouseup', handleGlobalMouseUp)
    }
  }, [isDragging])

  const handleProgressTouchStart = (e: React.TouchEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(true)
    const touch = e.touches[0]
    const newTime = calculateTimeFromEvent(touch.clientX)
    const audio = audioRef.current
    if (audio) {
      audio.currentTime = newTime
      setCurrentTime(newTime)
    }
  }

  const handleProgressTouchMove = (e: React.TouchEvent<HTMLDivElement>) => {
    if (!isDraggingRef.current) return
    e.preventDefault()
    const touch = e.touches[0]
    const newTime = calculateTimeFromEvent(touch.clientX)
    const audio = audioRef.current
    if (audio) {
      audio.currentTime = newTime
      setCurrentTime(newTime)
    }
  }

  const handleProgressTouchEnd = () => {
    setIsDragging(false)
  }

  return (
    <div style={{
      width: '100%',
      padding: '1rem',
      backgroundColor: '#f8f9fa',
      borderRadius: '8px',
      border: '1px solid #dee2e6'
    }}>
      <audio
        ref={audioRef}
        src={src}
        preload="metadata"
        style={{ display: 'none' }}
      />

      {/* Play/Pause Button */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '1rem',
        marginBottom: '0.75rem'
      }}>
        <button
          onClick={togglePlay}
          style={{
            width: '48px',
            height: '48px',
            borderRadius: '50%',
            border: 'none',
            backgroundColor: '#007bff',
            color: 'white',
            fontSize: '1.5rem',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            transition: 'background-color 0.2s'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = '#0056b3'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = '#007bff'
          }}
        >
          {isPlaying ? '⏸️' : '▶️'}
        </button>

        {/* Time Display */}
        <div style={{
          fontSize: '0.9rem',
          color: '#666',
          fontFamily: 'monospace',
          minWidth: '100px'
        }}>
          {formatTime(currentTime)} / {formatTime(duration)}
        </div>
      </div>

      {/* Progress Bar */}
      <div
        ref={progressRef}
        onClick={handleProgressClick}
        onMouseDown={handleProgressMouseDown}
        onTouchStart={handleProgressTouchStart}
        onTouchMove={handleProgressTouchMove}
        onTouchEnd={handleProgressTouchEnd}
        style={{
          width: '100%',
          height: '8px',
          backgroundColor: '#dee2e6',
          borderRadius: '4px',
          cursor: 'pointer',
          position: 'relative',
          marginBottom: '0.5rem',
          userSelect: 'none'
        }}
      >
        {/* Progress Fill */}
        <div
          style={{
            width: `${getProgressPercentage()}%`,
            height: '100%',
            backgroundColor: '#007bff',
            borderRadius: '4px',
            transition: isDragging ? 'none' : 'width 0.1s linear',
            position: 'relative'
          }}
        >
          {/* Progress Handle */}
          <div
            style={{
              position: 'absolute',
              right: '-6px',
              top: '50%',
              transform: 'translateY(-50%)',
              width: '16px',
              height: '16px',
              borderRadius: '50%',
              backgroundColor: '#007bff',
              border: '2px solid white',
              boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
              cursor: isDragging ? 'grabbing' : 'grab',
              transition: isDragging ? 'none' : 'all 0.1s',
              pointerEvents: 'auto'
            }}
            onMouseDown={(e) => {
              e.stopPropagation()
              setIsDragging(true)
            }}
          />
        </div>
      </div>
    </div>
  )
}

