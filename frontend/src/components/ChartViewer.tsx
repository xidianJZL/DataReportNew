import { useEffect, useRef } from 'react'
import * as echarts from 'echarts'

interface ChartViewerProps {
  config: Record<string, unknown>
  height?: number
}

export function ChartViewer({ config, height = 400 }: ChartViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<echarts.ECharts | null>(null)

  useEffect(() => {
    if (!containerRef.current) return

    // Initialize chart
    chartRef.current = echarts.init(containerRef.current)
    
    // Handle resize
    const handleResize = () => {
      chartRef.current?.resize()
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chartRef.current?.dispose()
    }
  }, [])

  useEffect(() => {
    if (chartRef.current && config) {
      chartRef.current.setOption(config, true)
    }
  }, [config])

  return (
    <div 
      ref={containerRef} 
      style={{ width: '100%', height: `${height}px` }}
      className="animate-fade-in"
    />
  )
}

// Parse chart config from markdown/code blocks
export function parseChartConfig(content: string): Record<string, unknown> | null {
  try {
    // Look for JSON-like chart configuration
    const jsonMatch = content.match(/```(?:json|javascript)\s*([\s\S]*?)\s*```/i)
    if (jsonMatch) {
      const parsed = JSON.parse(jsonMatch[1])
      if (parsed.option || parsed.chartOption) {
        return parsed.option || parsed.chartOption
      }
      return parsed
    }

    // Look for { option: {...} } pattern
    const optionMatch = content.match(/option\s*=\s*(\{[\s\S]*?\})\s*;/)
    if (optionMatch) {
      return JSON.parse(optionMatch[1])
    }

    return null
  } catch {
    return null
  }
}
