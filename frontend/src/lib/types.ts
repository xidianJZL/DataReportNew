export interface StreamEvent {
  type: string
  [key: string]: unknown
}

export interface AnalysisState {
  status: 'idle' | 'uploading' | 'analyzing' | 'complete' | 'error'
  currentStep: number
  maxSteps: number
  steps: Step[]
  finalReport: string
  error: string | null
}

export interface Step {
  id: number
  action: 'plan' | 'run_code' | 'finish' | 'error'
  analysis: string
  stepSummary?: string
  code?: string
  codeResult?: {
    stdout: string
    error: string | null
  }
  plan?: string[]
  finalAnswer?: string
}

export interface ModelConfig {
  base_url: string
  api_key: string
  model_name: string
}

export interface UploadedFile {
  file_id: string
  filename: string
  original_name: string
  size: number
  rows?: number
  columns?: string[]
  sample?: Record<string, unknown>[]
}
