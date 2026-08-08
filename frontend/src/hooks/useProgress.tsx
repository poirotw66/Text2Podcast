import { useEffect, useState, useRef } from 'react'
import { TaskStatus, podcastApi } from '../services/api'

interface UseProgressOptions {
  taskId: string | null
  // Bump this (e.g. with a counter) to force a fresh SSE connection, such as
  // after kicking off a background regeneration once the previous stream
  // already closed on completion.
  reconnectKey?: number | string
  onComplete?: () => void
  onError?: (error: string) => void
}

export const useProgress = ({ taskId, reconnectKey, onComplete, onError }: UseProgressOptions) => {
  const [status, setStatus] = useState<TaskStatus | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const eventSourceRef = useRef<EventSource | null>(null)
  
  // Store callbacks in refs to avoid re-creating connection on every render
  const onCompleteRef = useRef(onComplete)
  const onErrorRef = useRef(onError)
  
  // Update refs when callbacks change
  useEffect(() => {
    onCompleteRef.current = onComplete
    onErrorRef.current = onError
  }, [onComplete, onError])

  useEffect(() => {
    if (!taskId) {
      return
    }

    // Create SSE connection. Goes through podcastApi so the stream honours
    // VITE_API_URL like every other request -- this used to hardcode localhost:8000,
    // which silently broke progress updates against any non-local backend.
    const eventSource = new EventSource(podcastApi.getProgressStreamUrl(taskId))
    eventSourceRef.current = eventSource

    const handleOpen = () => {
      setIsConnected(true)
      console.log('SSE connection opened')
    }

    const handleMessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data)
        const newStatus: TaskStatus = {
          task_id: data.task_id,
          status: data.status,
          progress: data.progress,
          message: data.message,
          error: data.error,
          audio_file: data.audio_file,
          transcript_file: data.transcript_file,
          total_segments: data.total_segments,
          failed_segments: data.failed_segments,
          partial: data.partial,
        }
        console.log('SSE message received:', newStatus)
        setStatus(newStatus)

        // Handle completion
        if (newStatus.status === 'completed') {
          console.log('Task completed')
          eventSource.close()
          setIsConnected(false)
          onCompleteRef.current?.()
        }

        // Handle errors
        if (newStatus.status === 'failed') {
          console.log('Task failed:', newStatus.error)
          eventSource.close()
          setIsConnected(false)
          onErrorRef.current?.(newStatus.error || 'Task failed')
        }
      } catch (err) {
        console.error('Failed to parse SSE message:', err, event.data)
      }
    }

    const handleError = (err: Event) => {
      console.error('SSE error:', err)
      if (eventSource.readyState === EventSource.CLOSED) {
        setIsConnected(false)
        console.log('SSE connection closed')
      }
    }

    // Listen for 'progress' event (custom event name from backend)
    eventSource.addEventListener('progress', handleMessage as EventListener)
    eventSource.addEventListener('message', handleMessage)
    eventSource.onopen = handleOpen
    eventSource.onerror = handleError

    return () => {
      console.log('Cleaning up SSE connection')
      eventSource.removeEventListener('progress', handleMessage as EventListener)
      eventSource.removeEventListener('message', handleMessage)
      eventSource.close()
      eventSourceRef.current = null
      setIsConnected(false)
    }
  }, [taskId, reconnectKey])  // Depend on taskId + reconnectKey, not callbacks

  return { status, isConnected }
}

