import React, { useState, useEffect, useCallback, useRef } from 'react'
import { podcastApi, getErrorMessage, SegmentInfo, SegmentsResponse, TaskStatus } from '../services/api'
import { VOICES } from '../data/voices'
import { TONE_PRESETS, getTonePrompt } from '../data/tonePresets'
import { RefreshIcon, LoaderIcon, WarningIcon, CheckIcon } from './icons'

interface SegmentListProps {
  taskId: string
  status: TaskStatus | null
  // Tells the parent to open a fresh SSE connection, since the previous one
  // already closed after the first completion.
  onRegenerateStart: () => void
}

const STYLE_PROMPT_MAX_LENGTH = 200

export const SegmentList: React.FC<SegmentListProps> = ({ taskId, status, onRegenerateStart }) => {
  const [segmentsData, setSegmentsData] = useState<SegmentsResponse | null>(null)
  const [isLoadingSegments, setIsLoadingSegments] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [showFailedOnly, setShowFailedOnly] = useState(false)

  // Only one regeneration may be in flight at a time.
  const [isRegenerating, setIsRegenerating] = useState(false)
  const [regeneratingIndex, setRegeneratingIndex] = useState<number | null>(null)

  const [expandedIndex, setExpandedIndex] = useState<number | null>(null)
  const [formText, setFormText] = useState('')
  const [formVoice, setFormVoice] = useState('')
  const [formStylePrompt, setFormStylePrompt] = useState('')
  const [formError, setFormError] = useState<string | null>(null)

  const isCompleted = status?.status === 'completed'
  const prevStatusRef = useRef<string | undefined>(status?.status)

  const fetchSegments = useCallback(async () => {
    setIsLoadingSegments(true)
    setLoadError(null)
    try {
      const data = await podcastApi.getSegments(taskId)
      setSegmentsData(data)
    } catch (err) {
      setLoadError(getErrorMessage(err, 'Failed to load segment list'))
    } finally {
      setIsLoadingSegments(false)
    }
  }, [taskId])

  // Fetch on the first transition into 'completed', and again every time a
  // regeneration cycle finishes (status returns to 'completed' a second time).
  useEffect(() => {
    const prevStatus = prevStatusRef.current
    const currentStatus = status?.status

    if (currentStatus === 'completed' && prevStatus !== 'completed') {
      fetchSegments()
      setIsRegenerating(false)
      setRegeneratingIndex(null)
    }

    if (currentStatus === 'failed' && prevStatus !== 'failed' && isRegenerating) {
      setIsRegenerating(false)
      setRegeneratingIndex(null)
      setFormError(status?.error || 'Regeneration failed')
    }

    prevStatusRef.current = currentStatus
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status?.status])

  const handleOpenForm = (segment: SegmentInfo) => {
    if (isRegenerating) return
    setExpandedIndex(segment.index)
    setFormText(segment.text)
    setFormVoice(segment.voice)
    setFormStylePrompt('')
    setFormError(null)
  }

  const handleCancelForm = () => {
    setExpandedIndex(null)
    setFormError(null)
  }

  const handleApplyPreset = (presetId: string) => {
    if (!presetId) return
    setFormStylePrompt(getTonePrompt(presetId))
  }

  const handleRegenerateSubmit = async (segment: SegmentInfo) => {
    if (isRegenerating) return

    const trimmedStyle = formStylePrompt.trim()
    if (trimmedStyle.length > STYLE_PROMPT_MAX_LENGTH) {
      setFormError(`Style prompt must be ${STYLE_PROMPT_MAX_LENGTH} characters or fewer`)
      return
    }
    if (!formText.trim()) {
      setFormError('Text cannot be empty')
      return
    }

    setFormError(null)
    setIsRegenerating(true)
    setRegeneratingIndex(segment.index)

    try {
      await podcastApi.regenerateSegment(taskId, {
        segment_index: segment.index,
        text: formText,
        voice: formVoice,
        style_prompt: trimmedStyle || undefined,
      })
      setExpandedIndex(null)
      // Reopen the SSE stream; it closed after the initial completion.
      onRegenerateStart()
    } catch (err) {
      setFormError(getErrorMessage(err, 'Failed to start regeneration'))
      setIsRegenerating(false)
      setRegeneratingIndex(null)
    }
  }

  // Nothing to show yet: initial generation hasn't finished once, and we
  // have never had a segment list to display.
  if (!segmentsData && !isCompleted && !isRegenerating && !isLoadingSegments && !loadError) {
    return null
  }

  const segments = segmentsData?.segments ?? []
  const visibleSegments = showFailedOnly ? segments.filter((s) => !s.success) : segments

  return (
    <div style={{ marginTop: '2rem' }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '0.75rem',
        marginBottom: '1rem'
      }}>
        <h3 style={{
          fontSize: '1.3rem',
          fontWeight: '700',
          color: '#374151',
          margin: 0
        }}>
          Segments{segmentsData ? ` (${segmentsData.total} total, ${segmentsData.failed} failed)` : ''}
        </h3>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          {segmentsData && segmentsData.failed > 0 && (
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.9rem', color: '#374151', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={showFailedOnly}
                onChange={(e) => setShowFailedOnly(e.target.checked)}
              />
              Show failed only
            </label>
          )}
          <button
            type="button"
            onClick={fetchSegments}
            disabled={isLoadingSegments}
            aria-label="Refresh segment list"
            style={{
              padding: '0.5rem 0.9rem',
              backgroundColor: isLoadingSegments ? '#d1d5db' : '#6366f1',
              color: 'white',
              border: 'none',
              borderRadius: '0.375rem',
              fontSize: '0.85rem',
              fontWeight: '600',
              cursor: isLoadingSegments ? 'not-allowed' : 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.4rem'
            }}
          >
            {isLoadingSegments ? <LoaderIcon size={14} /> : <RefreshIcon size={14} />}
            Refresh
          </button>
        </div>
      </div>

      {isLoadingSegments && !segmentsData && (
        <p role="status" style={{ textAlign: 'center', color: '#6b7280', padding: '1rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}>
          <LoaderIcon size={16} />
          Loading segments…
        </p>
      )}

      {isRegenerating && (
        <div
          role="status"
          style={{
            marginBottom: '1rem',
            padding: '0.9rem 1.1rem',
            backgroundColor: '#eef2ff',
            border: '2px solid #6366f1',
            borderRadius: '0.5rem',
            color: '#3730a3',
            fontSize: '0.9rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem'
          }}
        >
          <LoaderIcon size={18} />
          <span>
            Regenerating segment {regeneratingIndex}… this calls the TTS service and may take a moment.
            Other regenerate actions are disabled until it finishes.
          </span>
        </div>
      )}

      {loadError && (
        <div style={{
          marginBottom: '1rem',
          padding: '0.9rem 1.1rem',
          backgroundColor: '#fef2f2',
          border: '2px solid #fecaca',
          borderRadius: '0.5rem',
          color: '#dc2626',
          fontSize: '0.9rem'
        }}>
          {loadError}
        </div>
      )}

      {segmentsData && (
        <div style={{
          maxHeight: '600px',
          overflowY: 'auto',
          border: '2px solid #e5e7eb',
          borderRadius: '0.75rem',
          padding: '1rem',
          backgroundColor: '#f9fafb'
        }}>
          {visibleSegments.length === 0 && (
            <p style={{ textAlign: 'center', color: '#6b7280', padding: '1rem' }}>
              No segments match this filter.
            </p>
          )}
          {visibleSegments.map((segment) => {
            const isExpanded = expandedIndex === segment.index
            const isThisRegenerating = isRegenerating && regeneratingIndex === segment.index
            const failedStyle = {
              backgroundColor: '#fef2f2',
              border: '2px solid #dc2626',
            }
            const okStyle = {
              backgroundColor: '#ffffff',
              border: '2px solid #e5e7eb',
            }
            const rowStyle = segment.success ? okStyle : failedStyle

            return (
              <div
                key={segment.index}
                style={{
                  marginBottom: '0.9rem',
                  padding: '1rem',
                  borderRadius: '0.5rem',
                  ...rowStyle
                }}
              >
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                  flexWrap: 'wrap',
                  gap: '0.5rem',
                  marginBottom: '0.5rem'
                }}>
                  <div>
                    <div style={{ fontWeight: '600', color: '#1f2937', fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      #{segment.index} · {segment.speaker} · voice: {segment.voice}
                      {segment.success ? (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', color: '#059669', fontSize: '0.8rem', fontWeight: '700' }}>
                          <CheckIcon size={14} /> OK
                        </span>
                      ) : (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', color: '#dc2626', fontSize: '0.8rem', fontWeight: '700' }}>
                          <WarningIcon size={14} /> Failed
                        </span>
                      )}
                    </div>
                    {!segment.success && segment.error && (
                      <div style={{ color: '#b91c1c', fontSize: '0.85rem', marginTop: '0.25rem' }}>
                        Error: {segment.error}
                      </div>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => (isExpanded ? handleCancelForm() : handleOpenForm(segment))}
                    disabled={isRegenerating}
                    aria-expanded={isExpanded}
                    aria-label={`Regenerate segment ${segment.index}`}
                    style={{
                      padding: '0.4rem 0.8rem',
                      backgroundColor: isRegenerating ? '#d1d5db' : '#6366f1',
                      color: 'white',
                      border: 'none',
                      borderRadius: '0.375rem',
                      fontSize: '0.8rem',
                      fontWeight: '600',
                      cursor: isRegenerating ? 'not-allowed' : 'pointer'
                    }}
                  >
                    {isThisRegenerating ? 'Regenerating…' : isExpanded ? 'Close' : 'Regenerate'}
                  </button>
                </div>

                {!isExpanded && (
                  <div style={{ color: '#374151', fontSize: '0.9rem', lineHeight: '1.5', whiteSpace: 'pre-wrap' }}>
                    {segment.text}
                  </div>
                )}

                {isExpanded && (
                  <div style={{ marginTop: '0.5rem', padding: '0.9rem', backgroundColor: '#f9fafb', borderRadius: '0.5rem', border: '1px solid #e5e7eb' }}>
                    <p style={{ marginBottom: '0.75rem', fontSize: '0.85rem', color: '#92400e', backgroundColor: '#fef3c7', padding: '0.5rem 0.75rem', borderRadius: '0.375rem' }}>
                      Regenerating this segment calls the text-to-speech service again (uses 1 TTS call).
                    </p>

                    <label htmlFor={`segment-text-${segment.index}`} style={{ display: 'block', fontWeight: '600', fontSize: '0.85rem', color: '#374151', marginBottom: '0.25rem' }}>
                      Text
                    </label>
                    <textarea
                      id={`segment-text-${segment.index}`}
                      value={formText}
                      onChange={(e) => setFormText(e.target.value)}
                      rows={3}
                      style={{
                        width: '100%',
                        padding: '0.6rem',
                        border: '2px solid #d1d5db',
                        borderRadius: '0.375rem',
                        fontFamily: 'inherit',
                        fontSize: '0.9rem',
                        marginBottom: '0.75rem',
                        resize: 'vertical'
                      }}
                    />

                    <label htmlFor={`segment-voice-${segment.index}`} style={{ display: 'block', fontWeight: '600', fontSize: '0.85rem', color: '#374151', marginBottom: '0.25rem' }}>
                      Voice
                    </label>
                    <select
                      id={`segment-voice-${segment.index}`}
                      value={formVoice}
                      onChange={(e) => setFormVoice(e.target.value)}
                      style={{
                        padding: '0.5rem 0.75rem',
                        border: '2px solid #d1d5db',
                        borderRadius: '0.375rem',
                        fontSize: '0.9rem',
                        marginBottom: '0.75rem',
                        minWidth: '220px'
                      }}
                    >
                      {VOICES.map((voice) => (
                        <option key={voice.name} value={voice.name}>{voice.name} ({voice.gender})</option>
                      ))}
                    </select>

                    <label htmlFor={`segment-preset-${segment.index}`} style={{ display: 'block', fontWeight: '600', fontSize: '0.85rem', color: '#374151', marginBottom: '0.25rem' }}>
                      Insert tone preset (optional)
                    </label>
                    <select
                      id={`segment-preset-${segment.index}`}
                      value=""
                      onChange={(e) => handleApplyPreset(e.target.value)}
                      style={{
                        padding: '0.5rem 0.75rem',
                        border: '2px solid #d1d5db',
                        borderRadius: '0.375rem',
                        fontSize: '0.9rem',
                        marginBottom: '0.75rem',
                        minWidth: '220px'
                      }}
                    >
                      <option value="">Choose a preset…</option>
                      {TONE_PRESETS.map((preset) => (
                        <option key={preset.id} value={preset.id}>{preset.label}</option>
                      ))}
                    </select>

                    <label htmlFor={`segment-style-${segment.index}`} style={{ display: 'block', fontWeight: '600', fontSize: '0.85rem', color: '#374151', marginBottom: '0.25rem' }}>
                      Style prompt (optional, max {STYLE_PROMPT_MAX_LENGTH} characters)
                    </label>
                    <input
                      id={`segment-style-${segment.index}`}
                      type="text"
                      value={formStylePrompt}
                      onChange={(e) => setFormStylePrompt(e.target.value)}
                      maxLength={STYLE_PROMPT_MAX_LENGTH}
                      placeholder="e.g. Speak warmly and conversationally"
                      style={{
                        width: '100%',
                        padding: '0.6rem',
                        border: '2px solid #d1d5db',
                        borderRadius: '0.375rem',
                        fontSize: '0.9rem',
                        marginBottom: '0.35rem'
                      }}
                    />
                    <div style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: '0.75rem' }}>
                      {formStylePrompt.length}/{STYLE_PROMPT_MAX_LENGTH}
                    </div>

                    {formError && (
                      <div style={{ marginBottom: '0.75rem', color: '#dc2626', fontSize: '0.85rem' }}>
                        {formError}
                      </div>
                    )}

                    <div style={{ display: 'flex', gap: '0.6rem', justifyContent: 'flex-end' }}>
                      <button
                        type="button"
                        onClick={handleCancelForm}
                        disabled={isRegenerating}
                        style={{
                          padding: '0.5rem 1rem',
                          backgroundColor: '#6b7280',
                          color: 'white',
                          border: 'none',
                          borderRadius: '0.375rem',
                          fontSize: '0.85rem',
                          fontWeight: '600',
                          cursor: isRegenerating ? 'not-allowed' : 'pointer'
                        }}
                      >
                        Cancel
                      </button>
                      <button
                        type="button"
                        onClick={() => handleRegenerateSubmit(segment)}
                        disabled={isRegenerating}
                        style={{
                          padding: '0.5rem 1rem',
                          backgroundColor: isRegenerating ? '#d1d5db' : '#10b981',
                          color: 'white',
                          border: 'none',
                          borderRadius: '0.375rem',
                          fontSize: '0.85rem',
                          fontWeight: '600',
                          cursor: isRegenerating ? 'not-allowed' : 'pointer',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.4rem'
                        }}
                      >
                        {isRegenerating && <LoaderIcon size={14} />}
                        Regenerate (uses 1 TTS call)
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
