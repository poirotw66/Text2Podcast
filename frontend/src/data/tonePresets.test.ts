import { describe, it, expect } from 'vitest'
import {
  TONE_PRESETS,
  DEFAULT_TONE_PRESET_ID,
  DEFAULT_TONE_SETTINGS,
  getTonePreset,
  getTonePrompt
} from './tonePresets'

describe('tonePresets', () => {
  it('resolves every preset to a non-empty prompt string', () => {
    expect(TONE_PRESETS.length).toBeGreaterThan(0)
    for (const preset of TONE_PRESETS) {
      const prompt = getTonePrompt(preset.id)
      expect(typeof prompt).toBe('string')
      expect(prompt.trim().length).toBeGreaterThan(0)
      expect(prompt).toBe(preset.prompt)
    }
  })

  it('defaults to the natural preset', () => {
    expect(DEFAULT_TONE_PRESET_ID).toBe('natural')
    expect(getTonePreset('natural')).toBeDefined()
    expect(DEFAULT_TONE_SETTINGS['Speaker 1']).toBe('natural')
    expect(DEFAULT_TONE_SETTINGS['Speaker 2']).toBe('natural')
  })

  it('falls back to the natural prompt for an unknown id without throwing', () => {
    expect(getTonePreset('totally-made-up-id')).toBeUndefined()
    expect(() => getTonePrompt('totally-made-up-id')).not.toThrow()
    expect(getTonePrompt('totally-made-up-id')).toBe(getTonePrompt(DEFAULT_TONE_PRESET_ID))
  })
})
