/**
 * API client for backend communication
 */
import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

export interface UploadRequest {
  text: string
  podcast_length_mode?: 'SHORT' | 'MEDIUM' | 'LONG'
}

export interface UploadResponse {
  task_id: string
  message: string
}

export interface TaskStatus {
  task_id: string
  status: 'pending' | 'processing' | 'step1' | 'step2' | 'step3' | 'completed' | 'failed'
  progress: number
  message?: string
  error?: string
  audio_file?: string
  transcript_file?: string
}

export const podcastApi = {
  /**
   * Upload text content and start podcast generation
   */
  async uploadText(text: string, podcastLengthMode: 'SHORT' | 'MEDIUM' | 'LONG' = 'MEDIUM'): Promise<UploadResponse> {
    const response = await api.post<UploadResponse>('/api/upload', { 
      text,
      podcast_length_mode: podcastLengthMode
    })
    return response.data
  },

  /**
   * Get task status
   */
  async getTaskStatus(taskId: string): Promise<TaskStatus> {
    const response = await api.get<TaskStatus>(`/api/status/${taskId}`)
    return response.data
  },

  /**
   * Download audio file
   */
  getAudioDownloadUrl(taskId: string): string {
    return `${API_BASE_URL}/api/download/${taskId}/audio`
  },

  /**
   * Download transcript file
   */
  getTranscriptDownloadUrl(taskId: string): string {
    return `${API_BASE_URL}/api/download/${taskId}/transcript`
  },

  /**
   * Get SSE stream URL for progress updates
   */
  getProgressStreamUrl(taskId: string): string {
    return `${API_BASE_URL}/api/stream/${taskId}`
  },

  /**
   * Step 1: Generate initial transcript
   */
  async step1GenerateInitialTranscript(taskId: string, podcastLengthMode?: 'SHORT' | 'MEDIUM' | 'LONG'): Promise<{ task_id: string; initial_transcript: string; message: string }> {
    const response = await api.post(`/api/step1/${taskId}`, {
      podcast_length_mode: podcastLengthMode
    })
    return response.data
  },

  /**
   * Step 2: Optimize transcript
   */
  async step2OptimizeTranscript(taskId: string, editedTranscript?: string): Promise<{ task_id: string; optimized_transcript: Array<[string, string]>; message: string }> {
    const response = await api.post('/api/step2', {
      task_id: taskId,
      edited_transcript: editedTranscript
    })
    return response.data
  },

  /**
   * Step 3: Generate audio
   */
  async step3GenerateAudio(
    taskId: string, 
    finalTranscript?: Array<[string, string]>,
    voiceSettings?: { 'Speaker 1': string; 'Speaker 2': string }
  ): Promise<TaskStatus> {
    const response = await api.post(`/api/step3/${taskId}`, {
      final_transcript: finalTranscript || null,
      voice_settings: voiceSettings || null
    })
    return response.data
  },

  /**
   * Get transcript content
   */
  async getTranscript(taskId: string): Promise<{ transcript: Array<[string, string]> }> {
    const response = await api.get(`/api/transcript/${taskId}`)
    return response.data
  },
}

