import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Eye, EyeOff, Settings } from 'lucide-react'
import type { ModelConfig } from '@/lib/types'

interface ModelConfigPanelProps {
  config: ModelConfig
  onChange: (config: ModelConfig) => void
  onTest?: () => void
}

export function ModelConfigPanel({ config, onChange, onTest }: ModelConfigPanelProps) {
  const [showApiKey, setShowApiKey] = useState(false)

  const handleChange = (field: keyof ModelConfig, value: string) => {
    onChange({ ...config, [field]: value })
  }

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center gap-2">
          <Settings className="h-5 w-5 text-muted-foreground" />
          <CardTitle className="text-lg">模型配置</CardTitle>
        </div>
        <CardDescription>
          配置 LLM API 连接信息
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <label className="text-sm font-medium">API 地址</label>
          <Input
            placeholder="https://api.openai.com/v1"
            value={config.base_url}
            onChange={(e) => handleChange('base_url', e.target.value)}
          />
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">API Key</label>
          <div className="relative">
            <Input
              type={showApiKey ? 'text' : 'password'}
              placeholder="sk-..."
              value={config.api_key}
              onChange={(e) => handleChange('api_key', e.target.value)}
              className="pr-10"
            />
            <button
              type="button"
              onClick={() => setShowApiKey(!showApiKey)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
            >
              {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">模型名称</label>
          <Input
            placeholder="gpt-4o"
            value={config.model_name}
            onChange={(e) => handleChange('model_name', e.target.value)}
          />
        </div>

        {onTest && (
          <Button variant="outline" onClick={onTest} className="w-full">
            测试连接
          </Button>
        )}
      </CardContent>
    </Card>
  )
}
