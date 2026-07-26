import { useEffect, useRef, useState } from 'react'
import mermaid from 'mermaid'

interface MermaidViewerProps {
  code: string
}

export function MermaidViewer({ code }: MermaidViewerProps) {
  const ref = useRef<HTMLDivElement>(null)
  const [svg, setSvg] = useState<string>('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!ref.current) return

    const renderDiagram = async () => {
      try {
        mermaid.initialize({
          startOnLoad: false,
          theme: 'default',
          securityLevel: 'loose',
          fontFamily: 'Inter, sans-serif',
        })
        
        const id = `mermaid-${Math.random().toString(36).substring(7)}`
        const result = await mermaid.render(id, code)
        setSvg(result.svg)
        setError(null)
      } catch (err) {
        setError(err instanceof Error ? err.message : '渲染失败')
      }
    }

    renderDiagram()
  }, [code])

  if (error) {
    return (
      <div className="text-destructive text-sm p-4 border border-destructive rounded-sm">
        Mermaid 渲染错误: {error}
      </div>
    )
  }

  return (
    <div 
      ref={ref} 
      className="flex justify-center my-4 animate-fade-in"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  )
}