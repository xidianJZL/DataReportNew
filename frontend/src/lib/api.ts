const API_BASE = '/api'

export interface ModelConfig {
  base_url: string
  api_key: string
  model_name: string
}

export interface FileInfo {
  file_id: string
  filename: string
  original_name: string
  size: number
  rows?: number
  columns?: string[]
  dtypes?: Record<string, string>
  sample?: Record<string, unknown>[]
  path?: string
  error?: string
}

export interface AnalysisStep {
  action: 'plan' | 'run_code' | 'finish' | 'error'
  analysis: string
  step_summary?: string
  code?: string
  code_result?: {
    stdout: string
    error: string | null
    result: unknown
  }
  plan?: string[]
  final_answer?: string
}

// API functions
export async function uploadFile(file: File): Promise<FileInfo> {
  const formData = new FormData()
  formData.append('file', file)
  
  const response = await fetch(`${API_BASE}/upload`, {
    method: 'POST',
    body: formData,
  })
  
  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || '上传失败')
  }
  
  return response.json()
}

// Real analyze call is handled by App.tsx via streaming fetch + manual SSE parsing
// (kept here as a typed reference for callers that may want a Promise<string> result)
export async function analyzeData(
  goal: string,
  modelConfig: ModelConfig,
  fileId?: string
): Promise<Response> {
  return fetch(`${API_BASE}/analyze`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      goal,
      llm_config: modelConfig,
      file_id: fileId,
    }),
  })
}

export async function getFileInfo(fileId: string): Promise<FileInfo> {
  const response = await fetch(`${API_BASE}/files/${fileId}`)
  
  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || '获取文件信息失败')
  }
  
  return response.json()
}

export async function deleteFile(fileId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/files/${fileId}`, {
    method: 'DELETE',
  })
  
  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || '删除失败')
  }
}

// Stream reader utility
export async function* readStream(
  reader: ReadableStreamDefaultReader<Uint8Array>
): AsyncGenerator<string, void, unknown> {
  const decoder = new TextDecoder()
  
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    yield decoder.decode(value, { stream: true })
  }
}
