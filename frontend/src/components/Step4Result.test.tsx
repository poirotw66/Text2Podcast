import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { Step4Result } from './Step4Result'
import type { TaskStatus } from '../services/api'

// Nothing here should touch the network: podcastApi is mocked wholesale.
// getSegments is included because Step4Result unconditionally mounts
// SegmentList underneath the result panel.
vi.mock('../services/api', () => ({
  podcastApi: {
    getAudioDownloadUrl: vi.fn((taskId: string) => `https://mock-api.example/api/download/${taskId}/audio`),
    getTranscriptDownloadUrl: vi.fn((taskId: string) => `https://mock-api.example/api/download/${taskId}/transcript`),
    getTranscript: vi.fn(() => Promise.resolve({ transcript: [] })),
    getSegments: vi.fn(() => Promise.resolve({ total: 0, failed: 0, segments: [] }))
  },
  getErrorMessage: vi.fn(() => 'mock error')
}))

const noop = () => {}

const partialStatus: TaskStatus = {
  task_id: 'task-partial',
  status: 'completed',
  progress: 100,
  message: 'Some lines could not be converted to audio.',
  total_segments: 5,
  failed_segments: 2,
  partial: true
}

const successStatus: TaskStatus = {
  task_id: 'task-success',
  status: 'completed',
  progress: 100,
  partial: false
}

describe('Step4Result partial-failure warning', () => {
  it('shows a warning naming the failed and total segment counts when partial is true', async () => {
    render(
      <Step4Result taskId="task-partial" status={partialStatus} onNewPodcast={noop} onRegenerateStart={noop} />
    )

    const alert = await screen.findByRole('alert')
    // The warning is not conveyed by colour alone: it carries a text label
    // (an explicit "Warning:" prefix) and is exposed via role="alert".
    expect(alert).toHaveTextContent(/warning/i)
    expect(alert).toHaveTextContent('2 of 5 segments failed to generate')
  })

  it('does not present the success state when partial is true', async () => {
    render(
      <Step4Result taskId="task-partial" status={partialStatus} onNewPodcast={noop} onRegenerateStart={noop} />
    )

    await screen.findByRole('alert')
    expect(screen.queryByText('Podcast Generated Successfully!')).not.toBeInTheDocument()
    expect(screen.getByText('Podcast Generated with Missing Segments')).toBeInTheDocument()
  })

  it('keeps the audio download available despite the partial failure', async () => {
    render(
      <Step4Result taskId="task-partial" status={partialStatus} onNewPodcast={noop} onRegenerateStart={noop} />
    )

    await screen.findByRole('alert')
    const downloadButton = screen.getByRole('button', { name: /download audio \(mp3\)/i })
    expect(downloadButton).toBeEnabled()
  })

  it('does not render the warning when the podcast completed without partial failure', async () => {
    render(
      <Step4Result taskId="task-success" status={successStatus} onNewPodcast={noop} onRegenerateStart={noop} />
    )

    await waitFor(() => expect(screen.getByText('Podcast Generated Successfully!')).toBeInTheDocument())
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
