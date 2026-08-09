import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { useProgress } from './useProgress'
import { podcastApi } from '../services/api'

// jsdom has no EventSource implementation, so useProgress's SSE connection
// has to be stubbed out entirely -- this also lets tests drive server
// messages by hand instead of needing a real backend.
class MockEventSource {
  static instances: MockEventSource[] = []
  static readonly CONNECTING = 0
  static readonly OPEN = 1
  static readonly CLOSED = 2

  url: string
  readyState = MockEventSource.CONNECTING
  onopen: (() => void) | null = null
  onerror: ((event: Event) => void) | null = null
  private listeners: Record<string, Array<(event: MessageEvent) => void>> = {}

  constructor(url: string) {
    this.url = url
    MockEventSource.instances.push(this)
  }

  addEventListener(type: string, callback: (event: MessageEvent) => void) {
    this.listeners[type] = this.listeners[type] ?? []
    this.listeners[type].push(callback)
  }

  removeEventListener(type: string, callback: (event: MessageEvent) => void) {
    this.listeners[type] = (this.listeners[type] ?? []).filter((cb) => cb !== callback)
  }

  close() {
    this.readyState = MockEventSource.CLOSED
  }

  emit(type: string, data: unknown) {
    const event = { data: JSON.stringify(data) } as MessageEvent
    for (const callback of this.listeners[type] ?? []) {
      callback(event)
    }
  }
}

vi.mock('../services/api', () => ({
  podcastApi: {
    getProgressStreamUrl: vi.fn((taskId: string) => `https://mock-api.example/api/stream/${taskId}`)
  }
}))

const mockedGetProgressStreamUrl = vi.mocked(podcastApi.getProgressStreamUrl)

beforeEach(() => {
  MockEventSource.instances = []
  vi.stubGlobal('EventSource', MockEventSource)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('useProgress SSE handling', () => {
  it('builds the stream URL from podcastApi.getProgressStreamUrl, not a hardcoded host', () => {
    renderHook(() => useProgress({ taskId: 'task-123' }))

    expect(mockedGetProgressStreamUrl).toHaveBeenCalledWith('task-123')
    expect(MockEventSource.instances).toHaveLength(1)
    expect(MockEventSource.instances[0].url).toBe('https://mock-api.example/api/stream/task-123')
    expect(MockEventSource.instances[0].url).not.toMatch(/localhost:8000/)
  })

  it('copies total_segments, failed_segments and partial off the event payload', async () => {
    const { result } = renderHook(() => useProgress({ taskId: 'task-456' }))
    const source = MockEventSource.instances[0]

    act(() => {
      source.emit('progress', {
        task_id: 'task-456',
        status: 'step3',
        progress: 80,
        total_segments: 12,
        failed_segments: 3,
        partial: true
      })
    })

    await waitFor(() => {
      expect(result.current.status).not.toBeNull()
    })
    expect(result.current.status?.total_segments).toBe(12)
    expect(result.current.status?.failed_segments).toBe(3)
    expect(result.current.status?.partial).toBe(true)
  })

  it('does not connect when taskId is null', () => {
    renderHook(() => useProgress({ taskId: null }))
    expect(MockEventSource.instances).toHaveLength(0)
  })
})
