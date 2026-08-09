import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SegmentList } from './SegmentList'
import { podcastApi } from '../services/api'
import type { TaskStatus, SegmentsResponse } from '../services/api'

vi.mock('../services/api', () => ({
  podcastApi: {
    getSegments: vi.fn(),
    regenerateSegment: vi.fn()
  },
  getErrorMessage: vi.fn(() => 'mock error')
}))

const mockedGetSegments = vi.mocked(podcastApi.getSegments)
const mockedRegenerateSegment = vi.mocked(podcastApi.regenerateSegment)

const fixtureSegments: SegmentsResponse = {
  total: 2,
  failed: 1,
  segments: [
    { index: 0, speaker: 'Speaker 1', text: 'Alpha line succeeded', voice: 'Kore', success: true, error: null },
    { index: 1, speaker: 'Speaker 2', text: 'Beta line failed', voice: 'Charon', success: false, error: 'TTS timed out' }
  ]
}

const completedStatus: TaskStatus = { task_id: 't1', status: 'completed', progress: 100 }

// SegmentList only fetches on a *transition* into 'completed' (see the
// component's effect comment), so tests render with a non-completed status
// first and then rerender as completed to trigger the real fetch path,
// exactly as the app does after Step 3 finishes.
async function renderCompleted() {
  const utils = render(<SegmentList taskId="t1" status={null} onRegenerateStart={vi.fn()} />)
  utils.rerender(<SegmentList taskId="t1" status={completedStatus} onRegenerateStart={vi.fn()} />)
  await screen.findByText('Alpha line succeeded')
  return utils
}

beforeEach(() => {
  mockedGetSegments.mockReset()
  mockedRegenerateSegment.mockReset()
  mockedGetSegments.mockResolvedValue(fixtureSegments)
})

describe('SegmentList failed-segment display and filter', () => {
  it('visually distinguishes failed segments from successful ones', async () => {
    await renderCompleted()

    expect(screen.getByText('OK')).toBeInTheDocument()
    expect(screen.getByText('Failed')).toBeInTheDocument()

    const okRow = screen.getByText('Alpha line succeeded').parentElement as HTMLElement
    const failedRow = screen.getByText('Beta line failed').parentElement as HTMLElement

    // Distinguished by more than just colour: a text/icon "Failed" badge is
    // present, and the row styling (border colour) also differs.
    expect(okRow.style.borderColor).not.toBe(failedRow.style.borderColor)
    expect(failedRow.style.borderColor).toMatch(/220, ?38, ?38/) // #dc2626
  })

  it('filters to only failed segments when "Show failed only" is checked', async () => {
    await renderCompleted()

    expect(screen.getByText('Alpha line succeeded')).toBeInTheDocument()
    expect(screen.getByText('Beta line failed')).toBeInTheDocument()

    const user = userEvent.setup()
    await user.click(screen.getByLabelText('Show failed only'))

    expect(screen.queryByText('Alpha line succeeded')).not.toBeInTheDocument()
    expect(screen.getByText('Beta line failed')).toBeInTheDocument()

    await user.click(screen.getByLabelText('Show failed only'))
    expect(screen.getByText('Alpha line succeeded')).toBeInTheDocument()
  })
})

describe('SegmentList regeneration in-flight guard', () => {
  it('disables regenerate controls while a regeneration is in flight', async () => {
    // Never resolves within the test, so the component stays in the
    // "regenerating" state for the duration of the assertions below --
    // this is what guards against double-charging for TTS calls.
    mockedRegenerateSegment.mockReturnValue(new Promise(() => {}))

    await renderCompleted()
    const user = userEvent.setup()

    await user.click(screen.getByRole('button', { name: 'Regenerate segment 1' }))
    const submitButton = screen.getByRole('button', { name: /regenerate \(uses 1 tts call\)/i })
    await user.click(submitButton)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Regenerate segment 0' })).toBeDisabled()
    })
    // aria-label is static ("Regenerate segment 1"), but the visible label
    // switches to "Regenerating…" and the button becomes disabled -- this is
    // the guard that prevents firing a second TTS call for the same segment.
    const segment1Button = screen.getByRole('button', { name: 'Regenerate segment 1' })
    expect(segment1Button).toBeDisabled()
    expect(segment1Button).toHaveTextContent('Regenerating…')
    expect(submitButton).toBeDisabled()
    expect(mockedRegenerateSegment).toHaveBeenCalledTimes(1)
  })
})
