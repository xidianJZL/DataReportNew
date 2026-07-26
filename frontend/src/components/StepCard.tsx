import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Code, Terminal, CheckCircle2, AlertCircle, FileText, Lightbulb, BarChart3 } from 'lucide-react'
import type { Step } from '@/lib/types'
import { cn } from '@/lib/utils'

interface StepCardProps {
  step: Step
  index: number
  isActive: boolean
}

export function StepCard({ step, index, isActive }: StepCardProps) {
  const getActionConfig = () => {
    switch (step.action) {
      case 'plan':
        return {
          icon: <Lightbulb className="h-4 w-4" />,
          label: '规划',
          color: 'bg-blue-100 text-blue-800',
        }
      case 'run_code':
        return {
          icon: <Code className="h-4 w-4" />,
          label: '执行代码',
          color: 'bg-purple-100 text-purple-800',
        }
      case 'finish':
        return {
          icon: <CheckCircle2 className="h-4 w-4" />,
          label: '完成',
          color: 'bg-green-100 text-green-800',
        }
      case 'error':
        return {
          icon: <AlertCircle className="h-4 w-4" />,
          label: '错误',
          color: 'bg-red-100 text-red-800',
        }
      default:
        return {
          icon: <FileText className="h-4 w-4" />,
          label: '执行',
          color: 'bg-gray-100 text-gray-800',
        }
    }
  }

  const actionConfig = getActionConfig()

  return (
    <Card 
      className={cn(
        "transition-all duration-300",
        isActive && "ring-2 ring-primary animate-pulse-subtle"
      )}
    >
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Badge className={actionConfig.color}>
              {actionConfig.icon}
              <span className="ml-1">{actionConfig.label}</span>
            </Badge>
            <span className="text-sm text-muted-foreground">步骤 {index + 1}</span>
          </div>
        </div>
        {step.analysis && (
          <CardTitle className="text-base font-normal text-muted-foreground mt-2">
            {step.analysis}
          </CardTitle>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        {step.plan && step.plan.length > 0 && (
          <div className="bg-muted rounded-sm p-4">
            <div className="flex items-center gap-2 mb-2 text-sm font-medium">
              <FileText className="h-4 w-4" />
              分析计划
            </div>
            <ul className="space-y-1 text-sm">
              {step.plan.map((item, i) => (
                <li key={i} className="flex items-start gap-2">
                  <span className="text-muted-foreground">{i + 1}.</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {step.code && (
          <div>
            <div className="flex items-center gap-2 mb-2 text-sm font-medium">
              <Code className="h-4 w-4" />
              执行的代码
            </div>
            <pre className="bg-slate-900 text-slate-50 p-4 rounded-sm overflow-x-auto text-xs">
              <code>{step.code}</code>
            </pre>
          </div>
        )}

        {step.codeResult && (
          <div>
            <div className="flex items-center gap-2 mb-2 text-sm font-medium">
              <Terminal className="h-4 w-4" />
              执行结果
            </div>
            {step.codeResult.stdout && (
              <pre className="bg-muted p-3 rounded-sm overflow-x-auto text-xs font-mono whitespace-pre-wrap">
                {step.codeResult.stdout}
              </pre>
            )}
            {step.codeResult.error && (
              <div className="bg-destructive/10 border border-destructive/30 text-destructive p-3 rounded-sm text-xs font-mono">
                {step.codeResult.error}
              </div>
            )}
          </div>
        )}

        {step.finalAnswer && (
          <div className="bg-cohere-pale-green border border-cohere-deep-green/20 rounded-sm p-4">
            <div className="flex items-center gap-2 mb-2 text-sm font-medium text-cohere-deep-green">
              <BarChart3 className="h-4 w-4" />
              分析报告
            </div>
            <div className="text-sm">
              {step.finalAnswer}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}