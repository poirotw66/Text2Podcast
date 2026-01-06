import React, { useState, useEffect, useRef } from 'react'
import { podcastApi } from '../services/api'
import { ProgressBar } from './ProgressBar'
import { AudioPlayer } from './AudioPlayer'
import { TaskStatus } from '../services/api'
import html2canvas from 'html2canvas'
import jsPDF from 'jspdf'

interface Step4ResultProps {
  taskId: string
  status: TaskStatus | null
  onNewPodcast: () => void
}

export const Step4Result: React.FC<Step4ResultProps> = ({ taskId, status, onNewPodcast }) => {
  const [transcript, setTranscript] = useState<Array<[string, string]>>([])
  const [loadingTranscript, setLoadingTranscript] = useState(false)
  const [isGeneratingPDF, setIsGeneratingPDF] = useState(false)
  const pdfRef = useRef<HTMLDivElement>(null)

  const handleDownloadAudio = () => {
    const url = podcastApi.getAudioDownloadUrl(taskId)
    const link = document.createElement('a')
    link.href = url
    link.download = `podcast_${taskId}.mp3`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const handleDownloadTranscript = async () => {
    if (transcript.length === 0) {
      alert('No transcript available to download')
      return
    }

    setIsGeneratingPDF(true)
    try {
      if (!pdfRef.current) {
        throw new Error('PDF container not found')
      }

      // Temporarily make the element visible for capture
      const originalStyle = {
        position: pdfRef.current.style.position,
        left: pdfRef.current.style.left,
        top: pdfRef.current.style.top,
        visibility: pdfRef.current.style.visibility,
        zIndex: pdfRef.current.style.zIndex,
        width: pdfRef.current.style.width
      }

      // Make element visible but off-screen for html2canvas
      pdfRef.current.style.position = 'fixed'
      pdfRef.current.style.left = '0px'
      pdfRef.current.style.top = '0px'
      pdfRef.current.style.visibility = 'visible'
      pdfRef.current.style.zIndex = '9999'
      pdfRef.current.style.width = '800px'

      // Wait for rendering
      await new Promise(resolve => setTimeout(resolve, 300))

      // Generate canvas from HTML with optimized settings
      const canvas = await html2canvas(pdfRef.current, {
        useCORS: true,
        logging: false,
        backgroundColor: '#ffffff',
        width: pdfRef.current.scrollWidth,
        height: pdfRef.current.scrollHeight,
        windowWidth: pdfRef.current.scrollWidth,
        windowHeight: pdfRef.current.scrollHeight,
        scale: 1.5, // Reduced from 2 to reduce file size
        allowTaint: false,
        removeContainer: false
      } as any)

      // Restore original style immediately
      pdfRef.current.style.position = originalStyle.position
      pdfRef.current.style.left = originalStyle.left
      pdfRef.current.style.top = originalStyle.top
      pdfRef.current.style.visibility = originalStyle.visibility
      pdfRef.current.style.zIndex = originalStyle.zIndex
      pdfRef.current.style.width = originalStyle.width

      // Check if canvas is empty
      if (canvas.width === 0 || canvas.height === 0) {
        throw new Error('Canvas is empty')
      }

      // Calculate PDF dimensions (A4: 210mm x 297mm)
      const pdfWidth = 210 // A4 width in mm
      const pdfHeight = 297 // A4 height in mm
      const margin = 10 // Top and bottom margin
      const usableHeight = pdfHeight - (margin * 2)
      const imgWidth = pdfWidth - (margin * 2)
      const imgHeight = (canvas.height * imgWidth) / canvas.width
      
      const pdf = new jsPDF('p', 'mm', 'a4')
      // Use JPEG format with quality 0.85 to reduce file size
      const imgData = canvas.toDataURL('image/jpeg', 0.85)

      // Get dialogue box positions for smart pagination
      const dialogueBoxes = pdfRef.current.querySelectorAll('.dialogue-box')
      const containerRect = pdfRef.current.getBoundingClientRect()
      const html2canvasScale = 1.5
      
      // Calculate pixel to mm conversion
      // canvas.width is already scaled (original * scale), so we need to account for that
      const originalHeight = pdfRef.current.scrollHeight
      const pxToMm = (px: number) => {
        // px is in original DOM pixels, convert to canvas pixels then to mm
        const canvasPx = px * html2canvasScale
        return (canvasPx * imgWidth) / canvas.width
      }
      
      // Get box positions in pixels (relative to container, in original DOM pixels)
      const boxPositions: Array<{ top: number; bottom: number; height: number }> = []
      dialogueBoxes.forEach((box) => {
        const rect = box.getBoundingClientRect()
        const relativeTop = rect.top - containerRect.top
        const relativeBottom = rect.bottom - containerRect.top
        boxPositions.push({
          top: relativeTop,
          bottom: relativeBottom,
          height: rect.height
        })
      })

      // Simple pagination: if content fits in one page
      if (imgHeight <= usableHeight) {
        pdf.addImage(imgData, 'JPEG', margin, margin, imgWidth, imgHeight)
        pdf.save(`transcript_${taskId}.pdf`)
        return
      }

      // Smart pagination: ensure dialogue boxes are not cut
      // pageBreaks are in original DOM pixels
      const pageBreaks: number[] = [0] // Start positions for each page (in original DOM pixels)
      
      // Convert usableHeight from mm to original DOM pixels
      const mmToPx = (mm: number) => {
        // Convert mm to canvas pixels, then to original DOM pixels
        const canvasPx = (mm * canvas.width) / imgWidth
        return canvasPx / html2canvasScale
      }
      
      const pageHeightPx = mmToPx(usableHeight) // Page height in original DOM pixels
      let currentPageStartPx = 0 // Current page start position
      let currentPageBottomPx = pageHeightPx // Current page bottom position
      
      // Process each dialogue box to ensure none are cut
      for (let i = 0; i < boxPositions.length; i++) {
        const box = boxPositions[i]
        const boxTopPx = box.top
        const boxBottomPx = box.bottom
        const boxHeightPx = box.height
        
        // Check if box would be cut by current page boundary
        const boxWouldBeCut = boxTopPx < currentPageBottomPx && boxBottomPx > currentPageBottomPx
        
        // Check if box fits completely on current page
        const boxFitsOnPage = boxTopPx >= currentPageStartPx && boxBottomPx <= currentPageBottomPx
        
        if (boxFitsOnPage) {
          // Box fits completely on current page, continue to next box
          continue
        } else if (boxWouldBeCut) {
          // Box would be cut - MUST start new page before this box
          // New page starts exactly at this box's top to ensure it's not cut
          if (pageBreaks.length === 0 || pageBreaks[pageBreaks.length - 1] !== boxTopPx) {
            pageBreaks.push(boxTopPx)
          }
          currentPageStartPx = boxTopPx
          currentPageBottomPx = boxTopPx + pageHeightPx
        } else if (boxTopPx >= currentPageBottomPx) {
          // Box is completely on next page - start new page
          if (pageBreaks.length === 0 || pageBreaks[pageBreaks.length - 1] !== boxTopPx) {
            pageBreaks.push(boxTopPx)
          }
          currentPageStartPx = boxTopPx
          currentPageBottomPx = boxTopPx + pageHeightPx
        }
        
        // Double-check: if box is taller than a page, ensure it starts on its own page
        if (boxHeightPx > pageHeightPx) {
          // Box is taller than a page - ensure it starts on its own page
          if (pageBreaks.length === 0 || pageBreaks[pageBreaks.length - 1] !== boxTopPx) {
            pageBreaks.push(boxTopPx)
          }
          currentPageStartPx = boxTopPx
          currentPageBottomPx = boxTopPx + pageHeightPx
        }
      }
      
      // Calculate the actual content end in original DOM pixels
      // Use the maximum of: last box bottom, originalHeight, or canvas height converted back
      let contentEndPx = originalHeight
      if (boxPositions.length > 0) {
        const lastBoxBottom = boxPositions[boxPositions.length - 1].bottom
        // No padding - use exact last box bottom
        contentEndPx = Math.max(contentEndPx, lastBoxBottom)
      }
      // Also ensure we use the full canvas height
      const canvasHeightInOriginalPx = canvas.height / html2canvasScale
      contentEndPx = Math.max(contentEndPx, canvasHeightInOriginalPx)
      
      // Debug: log page breaks and box positions to verify
      console.log('Page breaks:', pageBreaks)
      console.log('Content end:', contentEndPx)
      console.log('Box positions check:', boxPositions.map((b, i) => {
        const boxTop = b.top
        const boxBottom = b.bottom
        // Check which page this box would be on
        let pageIndex = 0
        for (let j = 0; j < pageBreaks.length; j++) {
          if (boxTop >= pageBreaks[j]) {
            pageIndex = j
          } else {
            break
          }
        }
        const pageStart = pageBreaks[pageIndex]
        const pageEnd = pageIndex < pageBreaks.length - 1 ? pageBreaks[pageIndex + 1] : contentEndPx
        const wouldBeCut = boxTop < pageEnd && boxBottom > pageEnd
        return {
          index: i,
          top: boxTop,
          bottom: boxBottom,
          height: b.height,
          pageIndex,
          pageStart,
          pageEnd,
          wouldBeCut
        }
      }))
      
      // Generate pages - verify no dialogue boxes are cut
      for (let i = 0; i < pageBreaks.length; i++) {
        if (i > 0) {
          pdf.addPage()
        }
        
        // pageBreaks are in original DOM pixels, convert to canvas pixels
        const startYOriginal = pageBreaks[i]
        
        // For the last page, use the calculated content end to ensure nothing is cut
        let endYOriginal: number
        if (i < pageBreaks.length - 1) {
          // Not the last page, use next break point
          endYOriginal = pageBreaks[i + 1]
        } else {
          // Last page: use the calculated content end, ensuring we include everything
          endYOriginal = contentEndPx
        }
        
        // Verify no dialogue box is cut by this page
        for (const box of boxPositions) {
          const boxTop = box.top
          const boxBottom = box.bottom
          // If box starts on this page but would be cut by page end
          if (boxTop >= startYOriginal && boxTop < endYOriginal && boxBottom > endYOriginal) {
            console.warn(`WARNING: Box would be cut! Box top: ${boxTop}, bottom: ${boxBottom}, page end: ${endYOriginal}`)
            // Adjust endYOriginal to include the full box
            endYOriginal = Math.max(endYOriginal, boxBottom)
          }
        }
        
        // Convert to canvas coordinates (scale 1.5)
        const startYCanvas = startYOriginal * html2canvasScale
        let endYCanvas = endYOriginal * html2canvasScale
        
        // For the last page, make sure we use the full canvas height if needed
        if (i === pageBreaks.length - 1) {
          // Last page: ensure we capture everything up to canvas height
          endYCanvas = Math.max(endYCanvas, canvas.height)
        }
        
        // Make sure we don't exceed canvas height
        endYCanvas = Math.min(endYCanvas, canvas.height)
        
        // Calculate actual page height in canvas pixels
        const actualPageHeightCanvas = endYCanvas - startYCanvas
        
        // Ensure pageHeight is positive
        if (actualPageHeightCanvas <= 0) {
          continue // Skip empty pages
        }
        
        // Calculate PDF dimensions - convert canvas pixels back to original pixels, then to mm
        const actualPageHeightOriginal = actualPageHeightCanvas / html2canvasScale
        const actualPageHeightMm = pxToMm(actualPageHeightOriginal)
        
        // Extract this page from canvas
        const pageCanvas = document.createElement('canvas')
        pageCanvas.width = canvas.width
        pageCanvas.height = Math.ceil(actualPageHeightCanvas)
        const ctx = pageCanvas.getContext('2d')
        
        if (ctx && actualPageHeightCanvas > 0) {
          // Draw the portion of the original canvas
          ctx.drawImage(
            canvas,
            0, startYCanvas,
            canvas.width, actualPageHeightCanvas,
            0, 0,
            canvas.width, actualPageHeightCanvas
          )
          // Use JPEG with quality 0.85 to reduce file size
          const pageImgData = pageCanvas.toDataURL('image/jpeg', 0.85)
          pdf.addImage(pageImgData, 'JPEG', margin, margin, imgWidth, actualPageHeightMm)
          
          // Debug: log page info
          console.log(`Page ${i + 1}:`, {
            startYOriginal,
            endYOriginal,
            startYCanvas,
            endYCanvas,
            actualPageHeightCanvas,
            actualPageHeightMm,
            isLastPage: i === pageBreaks.length - 1
          })
        }
      }

      pdf.save(`transcript_${taskId}.pdf`)
    } catch (error) {
      console.error('Failed to generate PDF:', error)
      alert('Failed to generate PDF. Please try again.')
    } finally {
      setIsGeneratingPDF(false)
    }
  }

  const isCompleted = status?.status === 'completed'
  // Always try to construct audio URL when completed, even if status.audio_file is not set
  const audioUrl = isCompleted ? podcastApi.getAudioDownloadUrl(taskId) : null

  useEffect(() => {
    if (isCompleted && transcript.length === 0 && !loadingTranscript) {
      setLoadingTranscript(true)
      podcastApi.getTranscript(taskId)
        .then((data) => {
          setTranscript(data.transcript)
        })
        .catch((error) => {
          console.error('Failed to load transcript:', error)
        })
        .finally(() => {
          setLoadingTranscript(false)
        })
    }
  }, [isCompleted, taskId, transcript.length, loadingTranscript])

  return (
    <div style={{ 
      maxWidth: '900px', 
      margin: '0 auto', 
      padding: '2rem',
      backgroundColor: 'white',
      borderRadius: '8px',
      boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
    }}>
      <h2 style={{ marginBottom: '1rem', textAlign: 'center' }}>Step 4: Your Podcast</h2>

      {!isCompleted && (
        <>
          <ProgressBar status={status} />
          <p style={{ textAlign: 'center', color: '#666', marginTop: '1rem' }}>
            Please wait while we generate your podcast...
          </p>
        </>
      )}

      {isCompleted && (
        <>
          <div style={{
            marginBottom: '2rem',
            padding: '1.5rem',
            backgroundColor: '#f0f8ff',
            borderRadius: '8px',
            border: '2px solid #28a745'
          }}>
            <h3 style={{ marginBottom: '1rem', color: '#28a745', textAlign: 'center' }}>
              ✓ Podcast Generated Successfully!
            </h3>
            
            {/* Audio Player - Always show when completed */}
            <div style={{ marginBottom: '2rem' }}>
              <label style={{ 
                display: 'block', 
                marginBottom: '0.5rem',
                fontWeight: '500',
                fontSize: '1.1rem'
              }}>
                🎧 Listen to your podcast:
              </label>
              {audioUrl ? (
                <AudioPlayer
                  src={audioUrl}
                  onError={(e) => {
                    console.error('Audio load error:', e)
                  }}
                />
              ) : (
                <div style={{ 
                  padding: '1rem', 
                  backgroundColor: '#fff3cd', 
                  border: '1px solid #ffc107',
                  borderRadius: '4px',
                  color: '#856404'
                }}>
                  Audio file is being prepared. Please try refreshing the page in a moment.
                </div>
              )}
            </div>

            {/* Transcript Display */}
            {transcript.length > 0 && (
              <>
                <div style={{ marginBottom: '2rem' }}>
                  <h3 style={{ 
                    marginBottom: '1rem', 
                    fontSize: '1.2rem',
                    fontWeight: '600',
                    color: '#333'
                  }}>
                    📝 Podcast Script:
                  </h3>
                  <div style={{
                    maxHeight: '600px',
                    overflowY: 'auto',
                    border: '1px solid #ddd',
                    borderRadius: '8px',
                    padding: '1rem',
                    backgroundColor: '#f9f9f9'
                  }}>
                    {transcript.map(([speaker, text], index) => {
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
                            boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
                          }}
                        >
                          <div style={{
                            fontWeight: '600',
                            marginBottom: '0.25rem',
                            color: titleColor,
                            fontSize: '1rem'
                          }}>
                            {speaker}:
                          </div>
                          <div style={{ color: '#212121', lineHeight: '1.6', fontSize: '0.95rem' }}>
                            {text}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>

                {/* Hidden div for PDF generation */}
                <div
                  ref={pdfRef}
                  style={{
                    position: 'fixed',
                    left: '-10000px',
                    top: 0,
                    width: '800px',
                    padding: '2rem',
                    backgroundColor: '#ffffff',
                    zIndex: -1,
                    visibility: 'hidden',
                    overflow: 'visible'
                  }}
                >
                  <h2 style={{
                    marginBottom: '1.5rem',
                    fontSize: '1.8rem',
                    fontWeight: '700',
                    color: '#333',
                    textAlign: 'center',
                    borderBottom: '2px solid #333',
                    paddingBottom: '0.5rem'
                  }}>
                    Podcast Transcript
                  </h2>
                  {transcript.map(([speaker, text], index) => {
                    const isSpeaker1 = speaker.includes('Speaker 1') || speaker.includes('講者 1') || speaker.includes('1')
                    const isSpeaker2 = speaker.includes('Speaker 2') || speaker.includes('講者 2') || speaker.includes('2')
                    
                    const speaker1Style = {
                      backgroundColor: '#e1f5fe',
                      borderLeft: '4px solid #0277bd',
                      borderColor: '#0277bd'
                    }
                    
                    const speaker2Style = {
                      backgroundColor: '#fff3e0',
                      borderLeft: '4px solid #ef6c00',
                      borderColor: '#ef6c00'
                    }
                    
                    const currentStyle = isSpeaker1 ? speaker1Style : (isSpeaker2 ? speaker2Style : {
                      backgroundColor: '#f5f5f5',
                      borderLeft: '4px solid #757575',
                      borderColor: '#757575'
                    })
                    
                    const titleColor = isSpeaker1 ? '#01579b' : (isSpeaker2 ? '#e65100' : '#424242')
                    
                    return (
                      <div
                        key={index}
                        className="dialogue-box"
                        style={{
                          marginBottom: '1rem',
                          padding: '0.75rem',
                          backgroundColor: currentStyle.backgroundColor,
                          borderRadius: '4px',
                          borderLeft: currentStyle.borderLeft,
                          border: `1px solid ${currentStyle.borderColor}`,
                          pageBreakInside: 'avoid',
                          breakInside: 'avoid'
                        }}
                      >
                        <div style={{
                          fontWeight: '600',
                          marginBottom: '0.25rem',
                          color: titleColor,
                          fontSize: '1rem'
                        }}>
                          {speaker}:
                        </div>
                        <div style={{
                          color: '#212121',
                          lineHeight: '1.6',
                          fontSize: '0.95rem',
                          whiteSpace: 'pre-wrap',
                          wordWrap: 'break-word'
                        }}>
                          {text}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </>
            )}

            {loadingTranscript && (
              <div style={{ textAlign: 'center', marginBottom: '2rem', color: '#666' }}>
                Loading transcript...
              </div>
            )}

            <div style={{ 
              display: 'flex', 
              gap: '1rem', 
              justifyContent: 'center',
              flexWrap: 'wrap'
            }}>
              <button
                onClick={handleDownloadAudio}
                style={{
                  padding: '0.75rem 2rem',
                  backgroundColor: '#28a745',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  fontSize: '1rem',
                  fontWeight: '500',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem'
                }}
              >
                <span>📥</span>
                Download Audio (MP3)
              </button>

              <button
                onClick={handleDownloadTranscript}
                disabled={isGeneratingPDF || transcript.length === 0}
                style={{
                  padding: '0.75rem 2rem',
                  backgroundColor: isGeneratingPDF ? '#6c757d' : '#007bff',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  fontSize: '1rem',
                  fontWeight: '500',
                  cursor: isGeneratingPDF ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  opacity: isGeneratingPDF ? 0.6 : 1
                }}
              >
                <span>{isGeneratingPDF ? '⏳' : '📄'}</span>
                {isGeneratingPDF ? 'Generating PDF...' : 'Download Transcript (PDF)'}
              </button>
            </div>
          </div>

          <div style={{ textAlign: 'center' }}>
            <button
              onClick={onNewPodcast}
              style={{
                padding: '0.75rem 2rem',
                backgroundColor: '#6c757d',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                fontSize: '1rem',
                fontWeight: '500',
                cursor: 'pointer'
              }}
            >
              Create Another Podcast
            </button>
          </div>
        </>
      )}
    </div>
  )
}

