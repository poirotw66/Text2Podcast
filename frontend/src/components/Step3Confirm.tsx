import React, { useState, useEffect } from 'react'

interface Step3ConfirmProps {
  optimizedTranscript: Array<[string, string]>
  onConfirm: () => void
  onBack: () => void
  onTranscriptChange?: (transcript: Array<[string, string]>) => void
}

export const Step3Confirm: React.FC<Step3ConfirmProps> = ({ 
  optimizedTranscript, 
  onConfirm, 
  onBack,
  onTranscriptChange
}) => {
  const [isGenerating, setIsGenerating] = useState(false)
  const [editableTranscript, setEditableTranscript] = useState<Array<[string, string]>>(optimizedTranscript)
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  const [editText, setEditText] = useState<string>('')

  useEffect(() => {
    setEditableTranscript(optimizedTranscript)
  }, [optimizedTranscript])

  const handleConfirm = async () => {
    setIsGenerating(true)
    // Update transcript before confirming
    if (onTranscriptChange) {
      onTranscriptChange(editableTranscript)
    }
    onConfirm()
  }

  const handleEdit = (index: number) => {
    setEditingIndex(index)
    setEditText(editableTranscript[index][1])
  }

  const handleSaveEdit = (index: number) => {
    const updated = [...editableTranscript]
    updated[index] = [updated[index][0], editText]
    setEditableTranscript(updated)
    setEditingIndex(null)
    setEditText('')
    if (onTranscriptChange) {
      onTranscriptChange(updated)
    }
  }

  const handleCancelEdit = () => {
    setEditingIndex(null)
    setEditText('')
  }

  const handleDelete = (index: number) => {
    if (window.confirm('確定要刪除這個對話框嗎？')) {
      const updated = editableTranscript.filter((_, i) => i !== index)
      setEditableTranscript(updated)
      if (onTranscriptChange) {
        onTranscriptChange(updated)
      }
    }
  }

  const handleAddNew = (index: number, speaker: string) => {
    const updated = [...editableTranscript]
    updated.splice(index + 1, 0, [speaker, ''])
    setEditableTranscript(updated)
    setEditingIndex(index + 1)
    setEditText('')
  }

  return (
    <div style={{ 
      maxWidth: '900px', 
      margin: '0 auto', 
      padding: '2.5rem',
      backgroundColor: 'rgba(255,255,255,0.95)',
      backdropFilter: 'blur(10px)',
      borderRadius: '1rem',
      boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1), 0 10px 10px -5px rgba(0,0,0,0.04)',
      border: '1px solid rgba(255,255,255,0.2)'
    }}>
      <h2 style={{ 
        marginBottom: '0.75rem', 
        textAlign: 'center',
        fontSize: '2rem',
        fontWeight: '700',
        color: '#1f2937',
        letterSpacing: '-0.02em'
      }}>
        Step 3: Confirm Final Script
      </h2>
      <p style={{ 
        marginBottom: '2rem', 
        color: '#6b7280', 
        textAlign: 'center',
        fontSize: '1.05rem'
      }}>
        Review and edit the optimized podcast script. Click "Generate Podcast" to create the audio.
      </p>

      <div style={{
        maxHeight: '550px',
        overflowY: 'auto',
        border: '2px solid #e5e7eb',
        borderRadius: '0.75rem',
        padding: '1.5rem',
        marginBottom: '2rem',
        backgroundColor: '#f9fafb'
      }}>
        {editableTranscript.map(([speaker, text], index) => {
          // Check if speaker is Speaker 1 or 講者 1 (support both English and Chinese)
          const isSpeaker1 = speaker.includes('Speaker 1') || speaker.includes('講者 1') || speaker.includes('1')
          const isSpeaker2 = speaker.includes('Speaker 2') || speaker.includes('講者 2') || speaker.includes('2')
          
          // More distinct colors for better differentiation
          const speaker1Style = {
            backgroundColor: '#e1f5fe', // Light blue background
            borderLeft: '4px solid #0277bd', // Dark blue border
            borderColor: '#0277bd'
          }
          
          const speaker2Style = {
            backgroundColor: '#fff3e0', // Light orange/amber background
            borderLeft: '4px solid #ef6c00', // Dark orange border
            borderColor: '#ef6c00'
          }
          
          const currentStyle = isSpeaker1 ? speaker1Style : (isSpeaker2 ? speaker2Style : {
            backgroundColor: '#f5f5f5',
            borderLeft: '4px solid #757575',
            borderColor: '#757575'
          })
          
          const titleColor = isSpeaker1 ? '#01579b' : (isSpeaker2 ? '#e65100' : '#424242')
          const isEditing = editingIndex === index
          
          return (
            <div 
              key={index}
              style={{
                marginBottom: '1.25rem',
                padding: '1rem',
                backgroundColor: currentStyle.backgroundColor,
                borderRadius: '0.5rem',
                borderLeft: currentStyle.borderLeft,
                border: `2px solid ${currentStyle.borderColor}`,
                boxShadow: isEditing ? '0 4px 12px rgba(0,0,0,0.15)' : '0 2px 6px rgba(0,0,0,0.08)',
                transition: 'all 0.2s ease',
                transform: isEditing ? 'scale(1.01)' : 'scale(1)'
              }}
            >
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: '0.5rem'
              }}>
                <div style={{
                  fontWeight: '600',
                  color: titleColor,
                  fontSize: '1rem'
                }}>
                  {speaker}:
                </div>
                {!isEditing && (
                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    <button
                      onClick={() => handleEdit(index)}
                      style={{
                        padding: '0.5rem 0.75rem',
                        backgroundColor: '#6366f1',
                        color: 'white',
                        border: 'none',
                        borderRadius: '0.375rem',
                        fontSize: '0.875rem',
                        fontWeight: '500',
                        cursor: 'pointer',
                        transition: 'all 0.2s ease',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.25rem'
                      }}
                      title="Edit"
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = '#4f46e5'
                        e.currentTarget.style.transform = 'translateY(-1px)'
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = '#6366f1'
                        e.currentTarget.style.transform = 'translateY(0)'
                      }}
                    >
                      ✏️ Edit
                    </button>
                    <button
                      onClick={() => handleDelete(index)}
                      style={{
                        padding: '0.5rem 0.75rem',
                        backgroundColor: '#ef4444',
                        color: 'white',
                        border: 'none',
                        borderRadius: '0.375rem',
                        fontSize: '0.875rem',
                        fontWeight: '500',
                        cursor: 'pointer',
                        transition: 'all 0.2s ease',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.25rem'
                      }}
                      title="Delete"
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = '#dc2626'
                        e.currentTarget.style.transform = 'translateY(-1px)'
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = '#ef4444'
                        e.currentTarget.style.transform = 'translateY(0)'
                      }}
                    >
                      🗑️ Delete
                    </button>
                    <button
                      onClick={() => handleAddNew(index, speaker)}
                      style={{
                        padding: '0.5rem 0.75rem',
                        backgroundColor: '#10b981',
                        color: 'white',
                        border: 'none',
                        borderRadius: '0.375rem',
                        fontSize: '0.875rem',
                        fontWeight: '500',
                        cursor: 'pointer',
                        transition: 'all 0.2s ease',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.25rem'
                      }}
                      title="Add New Dialogue Below"
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = '#059669'
                        e.currentTarget.style.transform = 'translateY(-1px)'
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = '#10b981'
                        e.currentTarget.style.transform = 'translateY(0)'
                      }}
                    >
                      ➕ Add
                    </button>
                  </div>
                )}
              </div>
              
              {isEditing ? (
                <div>
                  <textarea
                    value={editText}
                    onChange={(e) => setEditText(e.target.value)}
                    rows={5}
                    style={{
                      width: '100%',
                      padding: '0.75rem',
                      border: '2px solid #6366f1',
                      borderRadius: '0.5rem',
                      fontSize: '0.95rem',
                      fontFamily: 'inherit',
                      resize: 'vertical',
                      marginBottom: '0.75rem',
                      transition: 'all 0.2s ease',
                      backgroundColor: 'white',
                      color: '#1f2937',
                      lineHeight: '1.6'
                    }}
                    autoFocus
                    onFocus={(e) => {
                      e.currentTarget.style.boxShadow = '0 0 0 3px rgba(99,102,241,0.1)'
                    }}
                    onBlur={(e) => {
                      e.currentTarget.style.boxShadow = 'none'
                    }}
                  />
                  <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
                    <button
                      onClick={handleCancelEdit}
                      style={{
                        padding: '0.625rem 1.25rem',
                        backgroundColor: '#6b7280',
                        color: 'white',
                        border: 'none',
                        borderRadius: '0.5rem',
                        fontSize: '0.9rem',
                        fontWeight: '500',
                        cursor: 'pointer',
                        transition: 'all 0.2s ease'
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = '#4b5563'
                        e.currentTarget.style.transform = 'translateY(-1px)'
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = '#6b7280'
                        e.currentTarget.style.transform = 'translateY(0)'
                      }}
                    >
                      Cancel
                    </button>
                    <button
                      onClick={() => handleSaveEdit(index)}
                      disabled={!editText.trim()}
                      style={{
                        padding: '0.625rem 1.25rem',
                        backgroundColor: !editText.trim() ? '#d1d5db' : '#10b981',
                        color: 'white',
                        border: 'none',
                        borderRadius: '0.5rem',
                        fontSize: '0.9rem',
                        fontWeight: '500',
                        cursor: !editText.trim() ? 'not-allowed' : 'pointer',
                        transition: 'all 0.2s ease'
                      }}
                      onMouseEnter={(e) => {
                        if (editText.trim()) {
                          e.currentTarget.style.backgroundColor = '#059669'
                          e.currentTarget.style.transform = 'translateY(-1px)'
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (editText.trim()) {
                          e.currentTarget.style.backgroundColor = '#10b981'
                          e.currentTarget.style.transform = 'translateY(0)'
                        }
                      }}
                    >
                      Save
                    </button>
                  </div>
                </div>
              ) : (
                <div style={{ color: '#212121', lineHeight: '1.6', fontSize: '0.95rem' }}>
                  {text}
                </div>
              )}
            </div>
          )
        })}
      </div>

      <div style={{ display: 'flex', gap: '1rem', justifyContent: 'space-between' }}>
        <button
          onClick={onBack}
          disabled={isGenerating}
          style={{
            padding: '0.875rem 2rem',
            backgroundColor: isGenerating ? '#d1d5db' : '#6b7280',
            color: 'white',
            border: 'none',
            borderRadius: '0.5rem',
            fontSize: '1rem',
            fontWeight: '600',
            cursor: isGenerating ? 'not-allowed' : 'pointer',
            flex: 1,
            transition: 'all 0.2s ease',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.5rem'
          }}
          onMouseEnter={(e) => {
            if (!isGenerating) {
              e.currentTarget.style.backgroundColor = '#4b5563'
              e.currentTarget.style.transform = 'translateY(-2px)'
              e.currentTarget.style.boxShadow = '0 4px 6px rgba(0,0,0,0.1)'
            }
          }}
          onMouseLeave={(e) => {
            if (!isGenerating) {
              e.currentTarget.style.backgroundColor = '#6b7280'
              e.currentTarget.style.transform = 'translateY(0)'
              e.currentTarget.style.boxShadow = 'none'
            }
          }}
        >
          <span>←</span>
          Back
        </button>
        <button
          onClick={handleConfirm}
          disabled={isGenerating}
          style={{
            padding: '0.875rem 2rem',
            backgroundColor: isGenerating ? '#d1d5db' : '#10b981',
            color: 'white',
            border: 'none',
            borderRadius: '0.5rem',
            fontSize: '1rem',
            fontWeight: '600',
            cursor: isGenerating ? 'not-allowed' : 'pointer',
            flex: 2,
            transition: 'all 0.2s ease',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.5rem'
          }}
          onMouseEnter={(e) => {
            if (!isGenerating) {
              e.currentTarget.style.backgroundColor = '#059669'
              e.currentTarget.style.transform = 'translateY(-2px)'
              e.currentTarget.style.boxShadow = '0 10px 15px -3px rgba(16,185,129,0.3)'
            }
          }}
          onMouseLeave={(e) => {
            if (!isGenerating) {
              e.currentTarget.style.backgroundColor = '#10b981'
              e.currentTarget.style.transform = 'translateY(0)'
              e.currentTarget.style.boxShadow = 'none'
            }
          }}
        >
          {isGenerating ? (
            <>
              <span style={{ animation: 'spin 1s linear infinite' }}>⏳</span>
              Generating Podcast...
            </>
          ) : (
            <>
              <span>🎙️</span>
              Generate Podcast
            </>
          )}
        </button>
      </div>
    </div>
  )
}

