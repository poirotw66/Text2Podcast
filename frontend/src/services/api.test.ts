import { describe, it, expect } from 'vitest'
import { getErrorMessage } from './api'

// getErrorMessage is the single place error text shown to users comes from,
// so it's worth pinning its three branches directly rather than only
// exercising it incidentally through component tests.

function makeAxiosError(data: unknown): unknown {
  // axios.isAxiosError() only checks for `isAxiosError === true` on the
  // object, so a real network round trip isn't needed to satisfy it.
  return Object.assign(new Error('Request failed'), {
    isAxiosError: true,
    response: { status: 400, data }
  })
}

describe('getErrorMessage', () => {
  it('returns the backend detail for an axios error that carries one', () => {
    const err = makeAxiosError({ detail: 'Text field is required' })
    expect(getErrorMessage(err, 'fallback message')).toBe('Text field is required')
  })

  it('returns the fallback for a non-axios error', () => {
    const err = new Error('boom')
    expect(getErrorMessage(err, 'fallback message')).toBe('fallback message')
  })

  it('returns the fallback when the axios error response is malformed', () => {
    const missingDetail = makeAxiosError({ message: 'no detail field here' })
    expect(getErrorMessage(missingDetail, 'fallback message')).toBe('fallback message')

    const noResponse = Object.assign(new Error('network down'), { isAxiosError: true })
    expect(getErrorMessage(noResponse, 'fallback message')).toBe('fallback message')

    const emptyDetail = makeAxiosError({ detail: '' })
    expect(getErrorMessage(emptyDetail, 'fallback message')).toBe('fallback message')
  })
})
