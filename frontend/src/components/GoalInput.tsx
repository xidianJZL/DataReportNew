import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import { Send, Square, Sparkles } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'

interface GoalInputProps {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
  onCancel?: () => void
  isLoading: boolean
  disabled?: boolean
  placeholder?: string
}

const PRESET_GOALS = [
  '生成一份描述性统计分析报告，包含核心指标的可视化',
  '分析销售数据的趋势、季节性，并给出业务洞察',
  '对比不同分类的数据表现，识别关键差异',
  '进行相关性分析，找出影响核心指标的关键因素',
]

export function GoalInput({ 
  value, 
  onChange, 
  onSubmit, 
  onCancel,
  isLoading,
  disabled,
  placeholder = "描述你的数据分析需求..."
}: GoalInputProps) {
  return (
    <Card>
      <CardContent className="pt-6 space-y-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Sparkles className="h-4 w-4 text-primary" />
            <h3 className="font-medium">分析需求</h3>
          </div>
          <Textarea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            disabled={disabled || isLoading}
            className="min-h-[100px]"
          />
        </div>

        {!value && (
          <div>
            <p className="text-sm text-muted-foreground mb-2">示例需求：</p>
            <div className="flex flex-wrap gap-2">
              {PRESET_GOALS.map((goal, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => onChange(goal)}
                  className="text-xs px-3 py-1.5 rounded-pill border border-border hover:border-primary hover:text-primary transition-colors"
                  disabled={isLoading}
                >
                  {goal}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="flex justify-end gap-2">
          {isLoading && onCancel && (
            <Button variant="outline" onClick={onCancel}>
              <Square className="h-4 w-4 mr-2" />
              停止
            </Button>
          )}
          <Button 
            onClick={onSubmit} 
            disabled={!value.trim() || disabled || isLoading}
            size="lg"
          >
            <Send className="h-4 w-4 mr-2" />
            {isLoading ? '分析中...' : '开始分析'}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}