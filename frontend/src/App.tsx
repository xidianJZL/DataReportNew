import { useState, useRef, useCallback } from 'react'
import { BarChart3, Settings, FileUp, Play, AlertCircle, CheckCircle2 } from 'lucide-react'
import { ModelConfigPanel } from '@/components/ModelConfigPanel'
import { FileUpload } from '@/components/FileUpload'
import { GoalInput } from '@/components/GoalInput'
import { StepCard } from '@/components/StepCard'
import { MarkdownRenderer } from '@/components/MarkdownRenderer'
import { ThemeToggle } from '@/components/ThemeToggle'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { uploadFile } from '@/lib/api'
import { SSEReader } from '@/lib/stream'
import type { ModelConfig, UploadedFile, Step } from '@/lib/types'
import { cn } from '@/lib/utils'

const DEFAULT_CONFIG: ModelConfig = {
  base_url: 'https://api.openai.com/v1',
  api_key: '',
  model_name: 'gpt-4o',
}

export default function App() {
  const [modelConfig, setModelConfig] = useState<ModelConfig>(DEFAULT_CONFIG)
  const [file, setFile] = useState<UploadedFile | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [goal, setGoal] = useState('')
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [steps, setSteps] = useState<Step[]>([])
  const [currentStep, setCurrentStep] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [finalReport, setFinalReport] = useState<string>('')
  const [activeTab, setActiveTab] = useState<'process' | 'report'>('process')
  const abortControllerRef = useRef<AbortController | null>(null)

  const handleUpload = useCallback(async (selectedFile: File) => {
    setIsUploading(true)
    setError(null)
    try {
      const info = await uploadFile(selectedFile)
      setFile(info)
    } catch (err) {
      setError(err instanceof Error ? err.message : '上传失败')
    } finally {
      setIsUploading(false)
    }
  }, [])

  const handleAnalyze = useCallback(async () => {
    if (!goal.trim()) {
      setError('请输入分析需求')
      return
    }
    if (!modelConfig.base_url || !modelConfig.api_key) {
      setError('请配置模型 API')
      return
    }

    setIsAnalyzing(true)
    setSteps([])
    setCurrentStep(0)
    setFinalReport('')
    setError(null)
    setActiveTab('process')

    // Create AbortController for cancellation
    abortControllerRef.current = new AbortController()

    try {
      const response = await fetch('/api/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          goal,
          llm_config: modelConfig,
          file_id: file?.file_id,
        }),
        signal: abortControllerRef.current.signal,
      })

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || `HTTP ${response.status}`)
      }

      const reader = response.body
      if (!reader) throw new Error('No response body')

      // Delegate SSE framing to SSEReader (see @/lib/stream). The parser
      // handles chunk boundaries and multi-line data: fields per the SSE
      // spec, so UI code only deals with typed (event, data) pairs.
      for await (const evt of SSEReader.from(reader)) {
        let data: unknown
        try {
          data = evt.json()
        } catch (e) {
          console.error('Failed to parse stream data:', e, evt.data.slice(0, 200))
          continue
        }
        handleStreamEvent(evt.event, data)
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        setError('已取消分析')
      } else {
        setError(err instanceof Error ? err.message : '分析失败')
      }
    } finally {
      setIsAnalyzing(false)
      abortControllerRef.current = null
    }
  }, [goal, modelConfig, file])

  const handleStreamEvent = useCallback((eventType: string, data: any) => {

    if (eventType === 'step') {
      // Step start
      setCurrentStep(data.step)
      return
    }

    if (eventType === 'data' && data.action) {
      const stepData: Step = {
        id: steps.length + 1,
        action: data.action,
        analysis: data.analysis || '',
        stepSummary: data.step_summary,
        code: data.code,
        codeResult: data.code_result,
        plan: data.plan,
        finalAnswer: data.final_answer,
      }
      
      setSteps(prev => [...prev, stepData])
      
      if (data.action === 'finish' && data.final_answer) {
        setFinalReport(data.final_answer)
        setActiveTab('report')
      }
    }

    if (eventType === 'done') {
      setIsAnalyzing(false)
    }
  }, [steps])

  const handleCancel = useCallback(() => {
    abortControllerRef.current?.abort()
  }, [])

  const handleReset = useCallback(() => {
    setSteps([])
    setCurrentStep(0)
    setFinalReport('')
    setError(null)
    setActiveTab('process')
  }, [])

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-border bg-background/80 backdrop-blur-sm">
        <div className="container mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-sm bg-primary flex items-center justify-center">
              <BarChart3 className="h-5 w-5 text-primary-foreground" />
            </div>
            <div>
              <h1 className="font-display font-semibold text-lg leading-tight">DataReportNew</h1>
              <p className="text-xs text-muted-foreground">智能数据分析报告</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="container mx-auto px-6 py-8">
        {steps.length === 0 ? (
          // Setup View
          <div className="max-w-5xl mx-auto">
            {/* Hero Section */}
            <div className="text-center mb-12 animate-fade-in">
              <Badge variant="outline" className="mb-4">
                AI-Powered Analytics
              </Badge>
              <h2 className="font-display text-5xl font-normal tracking-tight mb-4">
                让数据自己
                <br />
                <span className="text-primary">讲述故事</span>
              </h2>
              <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
                上传数据表，描述你的分析需求，AI Agent 将自主规划、执行分析，并生成完整的可视化报告
              </p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Left Column - Configuration */}
              <div className="space-y-6">
                <ModelConfigPanel
                  config={modelConfig}
                  onChange={setModelConfig}
                />
                <FileUpload
                  file={file}
                  onFileChange={setFile}
                  onUpload={handleUpload}
                  isUploading={isUploading}
                />
              </div>

              {/* Right Column - Goal & Action */}
              <div className="space-y-6">
                <GoalInput
                  value={goal}
                  onChange={setGoal}
                  onSubmit={handleAnalyze}
                  onCancel={handleCancel}
                  isLoading={isAnalyzing}
                  disabled={!modelConfig.base_url || !modelConfig.api_key}
                />

                {error && (
                  <Card className="border-destructive">
                    <CardContent className="pt-6 flex items-start gap-2">
                      <AlertCircle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
                      <p className="text-sm text-destructive">{error}</p>
                    </CardContent>
                  </Card>
                )}

                {/* Feature Highlights */}
                <Card className="bg-cohere-soft-stone border-0">
                  <CardContent className="pt-6 space-y-4">
                    <div className="flex items-start gap-3">
                      <div className="h-8 w-8 rounded-sm bg-cohere-deep-green text-white flex items-center justify-center shrink-0">
                        <Play className="h-4 w-4" />
                      </div>
                      <div>
                        <h4 className="font-medium">自主规划</h4>
                        <p className="text-sm text-muted-foreground">LLM 自主制定计划、调用工具、迭代决策</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <div className="h-8 w-8 rounded-sm bg-cohere-action-blue text-white flex items-center justify-center shrink-0">
                        <FileUp className="h-4 w-4" />
                      </div>
                      <div>
                        <h4 className="font-medium">智能执行</h4>
                        <p className="text-sm text-muted-foreground">动态 Python 执行，实时分析反馈</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <div className="h-8 w-8 rounded-sm bg-cohere-coral text-white flex items-center justify-center shrink-0">
                        <BarChart3 className="h-4 w-4" />
                      </div>
                      <div>
                        <h4 className="font-medium">可视化报告</h4>
                        <p className="text-sm text-muted-foreground">基于 ECharts 的交互式图表与洞察</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>
          </div>
        ) : (
          // Analysis View
          <div className="max-w-5xl mx-auto">
            {/* Top Status Bar */}
            <div className="mb-6 flex items-center justify-between animate-fade-in">
              <div className="flex items-center gap-3">
                <Badge variant={isAnalyzing ? "info" : "success"}>
                  {isAnalyzing ? (
                    <>
                      <span className="animate-pulse-subtle">●</span>
                      <span className="ml-1">分析中</span>
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="h-3 w-3 mr-1" />
                      <span>已完成</span>
                    </>
                  )}
                </Badge>
                <span className="text-sm text-muted-foreground">
                  步骤 {currentStep} / 已完成 {steps.length}
                </span>
              </div>
              <Button variant="outline" onClick={handleReset}>
                新建分析
              </Button>
            </div>

            {/* Tabs */}
            <div className="flex border-b border-border mb-6">
              <button
                onClick={() => setActiveTab('process')}
                className={cn(
                  "px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px",
                  activeTab === 'process' 
                    ? "border-primary text-primary" 
                    : "border-transparent text-muted-foreground hover:text-foreground"
                )}
              >
                <Settings className="h-4 w-4 inline mr-2" />
                分析过程
              </button>
              <button
                onClick={() => setActiveTab('report')}
                disabled={!finalReport}
                className={cn(
                  "px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px",
                  activeTab === 'report' 
                    ? "border-primary text-primary" 
                    : "border-transparent text-muted-foreground hover:text-foreground",
                  !finalReport && "opacity-50 cursor-not-allowed"
                )}
              >
                <BarChart3 className="h-4 w-4 inline mr-2" />
                最终报告
                {finalReport && <Badge variant="secondary" className="ml-2">NEW</Badge>}
              </button>
            </div>

            {/* Content */}
            {activeTab === 'process' && (
              <div className="space-y-4 animate-fade-in">
                {steps.map((step, i) => (
                  <StepCard 
                    key={step.id} 
                    step={step} 
                    index={i}
                    isActive={i === steps.length - 1 && isAnalyzing}
                  />
                ))}
                {error && (
                  <Card className="border-destructive">
                    <CardContent className="pt-6 flex items-start gap-2">
                      <AlertCircle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
                      <p className="text-sm text-destructive">{error}</p>
                    </CardContent>
                  </Card>
                )}
              </div>
            )}

            {activeTab === 'report' && finalReport && (
              <Card className="animate-fade-in">
                <CardContent className="pt-6">
                  <MarkdownRenderer content={finalReport} />
                </CardContent>
              </Card>
            )}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-border mt-16 py-8 bg-cohere-soft-stone">
        <div className="container mx-auto px-6 text-center">
          <p className="text-sm text-muted-foreground">
            DataReportNew · 让 AI 成为你的数据分析师
          </p>
        </div>
      </footer>
    </div>
  )
}