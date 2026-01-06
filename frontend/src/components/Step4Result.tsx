import React, { useState, useEffect, useRef } from 'react'
import { podcastApi } from '../services/api'
import { ProgressBar } from './ProgressBar'
import { AudioPlayer } from './AudioPlayer'
import { TaskStatus } from '../services/api'
import html2canvas from 'html2canvas'
import jsPDF from 'jspdf'
import { DownloadIcon, FileTextIcon, CheckIcon, HeadphonesIcon, SparklesIcon, LoaderIcon } from './icons'

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
      let pageBreaks: number[] = [0] // Start positions for each page (in original DOM pixels)
      
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
      // Use the maximum of: last box bottom or originalHeight (but not canvas height to avoid blank space)
      let contentEndPx = originalHeight
      if (boxPositions.length > 0) {
        const lastBoxBottom = boxPositions[boxPositions.length - 1].bottom
        // Add small margin to ensure last box is fully visible
        contentEndPx = Math.max(contentEndPx, lastBoxBottom + 10) // Add 10px margin
      }
      // Don't use canvas.height here - it may include extra blank space
      // Instead, use the actual content height from the DOM element
      
      // Filter out page breaks that are beyond or equal to content end (prevents blank last page)
      pageBreaks = pageBreaks.filter(breakPos => breakPos < contentEndPx)
      
      // Ensure we have at least one page break (at 0)
      if (pageBreaks.length === 0) {
        pageBreaks = [0]
      }
      
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
        
        // Ensure endYOriginal is greater than startYOriginal (prevents blank page)
        if (endYOriginal <= startYOriginal) {
          continue // Skip this page if it would be empty
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
        
        // Double-check: ensure endYOriginal is still greater than startYOriginal after adjustments
        if (endYOriginal <= startYOriginal) {
          continue // Skip this page if it would be empty
        }
        
        // Convert to canvas coordinates (scale 1.5)
        let startYCanvas = startYOriginal * html2canvasScale
        let endYCanvas = endYOriginal * html2canvasScale
        
        // Ensure we don't exceed canvas height (prevents blank space)
        endYCanvas = Math.min(endYCanvas, canvas.height)
        
        // Ensure startYCanvas doesn't exceed canvas height (prevents blank last page)
        startYCanvas = Math.min(startYCanvas, canvas.height)
        
        // Calculate actual page height in canvas pixels
        const actualPageHeightCanvas = endYCanvas - startYCanvas
        
        // For the last page, check if it would be empty or too small BEFORE adding page
        if (i === pageBreaks.length - 1) {
          // Last page: ensure it has meaningful content (at least 50 pixels to avoid blank page)
          if (actualPageHeightCanvas <= 50) {
            console.warn(`Skipping last page: height too small (${actualPageHeightCanvas}px), startY: ${startYCanvas}, endY: ${endYCanvas}, canvas.height: ${canvas.height}`)
            continue // Skip if last page would be too small or empty
          }
        } else {
          // For non-last pages, ensure minimum height of 10 pixels
          if (actualPageHeightCanvas <= 10) {
            console.warn(`Skipping page ${i + 1}: height too small (${actualPageHeightCanvas}px)`)
            continue // Skip empty or too-small pages
          }
        }
        
        // Add page only if we have valid content
        if (i > 0) {
          pdf.addPage()
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
    <div className="glass-card" style={{ 
      maxWidth: '900px', 
      margin: '0 auto', 
      padding: '2.5rem',
      borderRadius: '1rem'
    }}>
      <h2 style={{ 
        marginBottom: '1.5rem', 
        textAlign: 'center',
        fontSize: '2rem',
        fontWeight: '700',
        color: '#1f2937',
        letterSpacing: '-0.02em'
      }}>
        Step 4: Your Podcast
      </h2>

      {!isCompleted && (
        <>
          <ProgressBar status={status} />
          <p style={{ 
            textAlign: 'center', 
            color: 'rgba(255,255,255,0.9)', 
            marginTop: '1.5rem',
            fontSize: '1.05rem',
            textShadow: '0 1px 3px rgba(0,0,0,0.2)'
          }}>
            Please wait while we generate your podcast...
          </p>
        </>
      )}

      {isCompleted && (
        <>
          <div style={{
            marginBottom: '2rem',
            padding: '2rem',
            background: 'linear-gradient(135deg, #dbeafe 0%, #e0f2fe 100%)',
            borderRadius: '1rem',
            border: '3px solid #10b981',
            boxShadow: '0 10px 15px -3px rgba(16,185,129,0.2)'
          }}>
            <h3 style={{ 
              marginBottom: '1.5rem', 
              color: '#059669', 
              textAlign: 'center',
              fontSize: '1.5rem',
              fontWeight: '700',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.5rem'
            }}>
              <CheckIcon size={28} />
              Podcast Generated Successfully!
            </h3>
            
            {/* Audio Player - Always show when completed */}
            <div style={{ marginBottom: '2rem' }}>
              <label style={{ 
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                marginBottom: '0.75rem',
                fontWeight: '600',
                fontSize: '1.15rem',
                color: '#374151'
              }}>
                <HeadphonesIcon size={20} />
                Listen to your podcast:
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
                  padding: '1.25rem', 
                  backgroundColor: '#fef3c7', 
                  border: '2px solid #f59e0b',
                  borderRadius: '0.5rem',
                  color: '#92400e',
                  fontSize: '0.95rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem'
                }}>
                  <LoaderIcon size={20} />
                  <span>Audio file is being prepared. Please try refreshing the page in a moment.</span>
                </div>
              )}
            </div>

            {/* Transcript Display */}
            {transcript.length > 0 && (
              <>
                <div style={{ marginBottom: '2rem' }}>
                  <h3 style={{ 
                    marginBottom: '1rem', 
                    fontSize: '1.3rem',
                    fontWeight: '700',
                    color: '#374151',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem'
                  }}>
                    <FileTextIcon size={24} />
                    Podcast Script:
                  </h3>
                  <div style={{
                    maxHeight: '600px',
                    overflowY: 'auto',
                    border: '2px solid #e5e7eb',
                    borderRadius: '0.75rem',
                    padding: '1.5rem',
                    backgroundColor: '#f9fafb'
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
                            marginBottom: '1.25rem',
                            padding: '1rem',
                            backgroundColor: currentStyle.backgroundColor,
                            borderRadius: '0.5rem',
                            borderLeft: currentStyle.borderLeft,
                            border: `2px solid ${currentStyle.borderColor}`,
                            boxShadow: '0 2px 6px rgba(0,0,0,0.08)',
                            transition: 'all 0.2s ease'
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
              <div style={{ 
                textAlign: 'center', 
                marginBottom: '2rem', 
                color: '#6b7280',
                padding: '1rem',
                backgroundColor: '#f9fafb',
                borderRadius: '0.5rem',
                fontSize: '0.95rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.5rem'
              }}>
                <LoaderIcon size={20} />
                Loading transcript...
              </div>
            )}

            <div style={{ 
              display: 'flex', 
              gap: '1rem', 
              justifyContent: 'center',
              flexWrap: 'wrap',
              marginBottom: '2rem'
            }}>
              <button
                onClick={handleDownloadAudio}
                style={{
                  padding: '0.875rem 2rem',
                  backgroundColor: '#10b981',
                  color: 'white',
                  border: 'none',
                  borderRadius: '0.5rem',
                  fontSize: '1rem',
                  fontWeight: '600',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  transition: 'all 0.2s ease'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = '#059669'
                  e.currentTarget.style.transform = 'translateY(-2px)'
                  e.currentTarget.style.boxShadow = '0 10px 15px -3px rgba(16,185,129,0.3)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = '#10b981'
                  e.currentTarget.style.transform = 'translateY(0)'
                  e.currentTarget.style.boxShadow = 'none'
                }}
              >
                <DownloadIcon size={20} />
                Download Audio (MP3)
              </button>

              <button
                onClick={handleDownloadTranscript}
                disabled={isGeneratingPDF || transcript.length === 0}
                style={{
                  padding: '0.875rem 2rem',
                  backgroundColor: isGeneratingPDF || transcript.length === 0 ? '#d1d5db' : '#6366f1',
                  color: 'white',
                  border: 'none',
                  borderRadius: '0.5rem',
                  fontSize: '1rem',
                  fontWeight: '600',
                  cursor: isGeneratingPDF || transcript.length === 0 ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  transition: 'all 0.2s ease'
                }}
                onMouseEnter={(e) => {
                  if (!isGeneratingPDF && transcript.length > 0) {
                    e.currentTarget.style.backgroundColor = '#4f46e5'
                    e.currentTarget.style.transform = 'translateY(-2px)'
                    e.currentTarget.style.boxShadow = '0 10px 15px -3px rgba(99,102,241,0.3)'
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isGeneratingPDF && transcript.length > 0) {
                    e.currentTarget.style.backgroundColor = '#6366f1'
                    e.currentTarget.style.transform = 'translateY(0)'
                    e.currentTarget.style.boxShadow = 'none'
                  }
                }}
              >
                {isGeneratingPDF ? <LoaderIcon size={20} /> : <FileTextIcon size={20} />}
                {isGeneratingPDF ? 'Generating PDF...' : 'Download Transcript (PDF)'}
              </button>
            </div>
          </div>

          <div style={{ textAlign: 'center' }}>
            <button
              onClick={onNewPodcast}
              style={{
                padding: '0.875rem 2rem',
                backgroundColor: '#6b7280',
                color: 'white',
                border: 'none',
                borderRadius: '0.5rem',
                fontSize: '1rem',
                fontWeight: '600',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.5rem'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = '#4b5563'
                e.currentTarget.style.transform = 'translateY(-2px)'
                e.currentTarget.style.boxShadow = '0 4px 6px rgba(0,0,0,0.1)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = '#6b7280'
                e.currentTarget.style.transform = 'translateY(0)'
                e.currentTarget.style.boxShadow = 'none'
              }}
            >
              <SparklesIcon size={20} />
              Create Another Podcast
            </button>
          </div>
        </>
      )}
    </div>
  )
}

