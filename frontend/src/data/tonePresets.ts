// Tone/style presets for TTS generation.
// The preset list is frontend-owned (see API_CONTRACT.md section 3): we send
// the English prompt string as `style_settings[speaker]` on Step3Request and
// on the regenerate endpoint's `style_prompt`. Keep this the single place
// these ids/labels/prompts are defined.

export interface TonePreset {
  id: string
  label: string
  prompt: string
}

export const TONE_PRESETS: TonePreset[] = [
  { id: 'natural', label: '自然（預設）', prompt: 'Say the following naturally' },
  { id: 'warm', label: '親切溫暖', prompt: 'Speak warmly and conversationally, with a friendly tone' },
  { id: 'professional', label: '專業沉穩', prompt: 'Speak in a calm, professional, measured tone' },
  { id: 'energetic', label: '活潑有活力', prompt: 'Speak with energy and enthusiasm' },
  { id: 'curious', label: '好奇提問', prompt: 'Speak with curiosity, as if genuinely interested and asking questions' },
]

export const DEFAULT_TONE_PRESET_ID = 'natural'

export const DEFAULT_TONE_SETTINGS = {
  'Speaker 1': DEFAULT_TONE_PRESET_ID,
  'Speaker 2': DEFAULT_TONE_PRESET_ID,
}

export const getTonePreset = (id: string): TonePreset | undefined =>
  TONE_PRESETS.find((preset) => preset.id === id)

// Resolve a stored preset id to the prompt string sent to the API. Falls
// back to the natural preset's prompt for an unrecognized id.
export const getTonePrompt = (id: string): string =>
  getTonePreset(id)?.prompt ?? (getTonePreset(DEFAULT_TONE_PRESET_ID) as TonePreset).prompt
