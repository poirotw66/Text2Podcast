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
      padding: '2rem',
      backgroundColor: 'white',
      borderRadius: '8px',
      boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
    }}>
      <h2 style={{ marginBottom: '1rem', textAlign: 'center' }}>Step 3: Confirm Final Script</h2>
      <p style={{ marginBottom: '1.5rem', color: '#666', textAlign: 'center' }}>
        Review and edit the optimized podcast script. Click "Generate Podcast" to create the audio.
      </p>

      <div style={{
        maxHeight: '500px',
        overflowY: 'auto',
        border: '1px solid #ddd',
        borderRadius: '4px',
        padding: '1rem',
        marginBottom: '1.5rem',
        backgroundColor: '#f9f9f9'
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
                marginBottom: '1rem',
                padding: '0.75rem',
                backgroundColor: currentStyle.backgroundColor,
                borderRadius: '4px',
                borderLeft: currentStyle.borderLeft,
                border: `1px solid ${currentStyle.borderColor}`,
                boxShadow: isEditing ? '0 2px 6px rgba(0,0,0,0.2)' : '0 1px 3px rgba(0,0,0,0.1)',
                transition: 'all 0.2s ease'
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
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button
                      onClick={() => handleEdit(index)}
                      style={{
                        padding: '0.25rem 0.5rem',
                        backgroundColor: '#007bff',
                        color: 'white',
                        border: 'none',
                        borderRadius: '3px',
                        fontSize: '0.85rem',
                        cursor: 'pointer'
                      }}
                      title="編輯"
                    >
                      ✏️ 編輯
                    </button>
                    <button
                      onClick={() => handleDelete(index)}
                      style={{
                        padding: '0.25rem 0.5rem',
                        backgroundColor: '#dc3545',
                        color: 'white',
                        border: 'none',
                        borderRadius: '3px',
                        fontSize: '0.85rem',
                        cursor: 'pointer'
                      }}
                      title="刪除"
                    >
                      🗑️ 刪除
                    </button>
                    <button
                      onClick={() => handleAddNew(index, speaker)}
                      style={{
                        padding: '0.25rem 0.5rem',
                        backgroundColor: '#28a745',
                        color: 'white',
                        border: 'none',
                        borderRadius: '3px',
                        fontSize: '0.85rem',
                        cursor: 'pointer'
                      }}
                      title="在下方新增對話"
                    >
                      ➕ 新增
                    </button>
                  </div>
                )}
              </div>
              
              {isEditing ? (
                <div>
                  <textarea
                    value={editText}
                    onChange={(e) => setEditText(e.target.value)}
                    rows={4}
                    style={{
                      width: '100%',
                      padding: '0.5rem',
                      border: '2px solid #007bff',
                      borderRadius: '4px',
                      fontSize: '0.95rem',
                      fontFamily: 'inherit',
                      resize: 'vertical',
                      marginBottom: '0.5rem'
                    }}
                    autoFocus
                  />
                  <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                    <button
                      onClick={handleCancelEdit}
                      style={{
                        padding: '0.5rem 1rem',
                        backgroundColor: '#6c757d',
                        color: 'white',
                        border: 'none',
                        borderRadius: '4px',
                        fontSize: '0.9rem',
                        cursor: 'pointer'
                      }}
                    >
                      取消
                    </button>
                    <button
                      onClick={() => handleSaveEdit(index)}
                      disabled={!editText.trim()}
                      style={{
                        padding: '0.5rem 1rem',
                        backgroundColor: !editText.trim() ? '#ccc' : '#28a745',
                        color: 'white',
                        border: 'none',
                        borderRadius: '4px',
                        fontSize: '0.9rem',
                        cursor: !editText.trim() ? 'not-allowed' : 'pointer'
                      }}
                    >
                      保存
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
            padding: '0.75rem 2rem',
            backgroundColor: isGenerating ? '#ccc' : '#6c757d',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            fontSize: '1rem',
            fontWeight: '500',
            cursor: isGenerating ? 'not-allowed' : 'pointer',
            flex: 1
          }}
        >
          ← Back
        </button>
        <button
          onClick={handleConfirm}
          disabled={isGenerating}
          style={{
            padding: '0.75rem 2rem',
            backgroundColor: isGenerating ? '#ccc' : '#28a745',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            fontSize: '1rem',
            fontWeight: '500',
            cursor: isGenerating ? 'not-allowed' : 'pointer',
            flex: 2
          }}
        >
          {isGenerating ? 'Generating Podcast...' : '🎙️ Generate Podcast'}
        </button>
      </div>
    </div>
  )
}

