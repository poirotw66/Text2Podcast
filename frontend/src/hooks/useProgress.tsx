import { useEffect, useState, useRef } from 'react'
import { TaskStatus } from '../services/api'

interface UseProgressOptions {
  taskId: string | null
  onComplete?: () => void
  onError?: (error: string) => void
}

export const useProgress = ({ taskId, onComplete, onError }: UseProgressOptions) => {
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

    // Create SSE connection
    const eventSource = new EventSource(
      `http://localhost:8000/api/stream/${taskId}`
    )
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
  }, [taskId])  // Only depend on taskId, not callbacks

  return { status, isConnected }
}

