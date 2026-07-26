import { useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import { parseChartConfig, ChartViewer } from './ChartViewer'
import { MermaidViewer } from './MermaidViewer'
import { cn } from '@/lib/utils'

interface MarkdownRendererProps {
  content: string
  className?: string
}

type Section =
  | { type: 'markdown'; content: string }
  | { type: 'chart'; content: string }
  | { type: 'mermaid'; content: string }

export function MarkdownRenderer({ content, className }: MarkdownRendererProps) {
  const sections = useMemo<Section[]>(() => {
    const parts: Section[] = []

    // Match ```echarts|json|javascript|js code blocks for ECharts
    // and ```mermaid code blocks for Mermaid
    const codeBlockRegex = /```(echarts|json|javascript|js|mermaid)\s*([\s\S]*?)\s*```/gi
    let lastIndex = 0
    let match: RegExpExecArray | null

    while ((match = codeBlockRegex.exec(content)) !== null) {
      const lang = match[1].toLowerCase()
      const inner = match[2].trim()

      if (match.index > lastIndex) {
        const markdown = content.slice(lastIndex, match.index).trim()
        if (markdown) parts.push({ type: 'markdown', content: markdown })
      }

      if (lang === 'mermaid') {
        parts.push({ type: 'mermaid', content: inner })
      } else {
        parts.push({ type: 'chart', content: inner })
      }

      lastIndex = match.index + match[0].length
    }

    if (lastIndex < content.length) {
      const markdown = content.slice(lastIndex).trim()
      if (markdown) parts.push({ type: 'markdown', content: markdown })
    }

    return parts
  }, [content])

  return (
    <div className={cn('markdown-content', className)}>
      {sections.map((section, index) => {
        if (section.type === 'chart') {
          const config = parseChartConfig(section.content)
          if (config) {
            return (
              <ChartViewer
                key={index}
                config={config}
                height={400}
              />
            )
          }
          // Fallback: render raw code block if parsing failed
          return (
            <pre key={index} className="bg-muted p-4 rounded-sm overflow-x-auto mb-4 text-sm font-mono">
              <code>{section.content}</code>
            </pre>
          )
        }

        if (section.type === 'mermaid') {
          return <MermaidViewer key={index} code={section.content} />
        }

        return (
          <ReactMarkdown
            key={index}
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[rehypeRaw]}
            components={{
              h1: ({ children }) => (
                <h1 className="text-3xl font-display font-semibold mb-4 mt-6">
                  {children}
                </h1>
              ),
              h2: ({ children }) => (
                <h2 className="text-2xl font-display font-semibold mb-3 mt-5">
                  {children}
                </h2>
              ),
              h3: ({ children }) => (
                <h3 className="text-xl font-display font-medium mb-2 mt-4">
                  {children}
                </h3>
              ),
              p: ({ children }) => (
                <p className="mb-4 leading-relaxed">{children}</p>
              ),
              ul: ({ children }) => (
                <ul className="mb-4 pl-6 list-disc">{children}</ul>
              ),
              ol: ({ children }) => (
                <ol className="mb-4 pl-6 list-decimal">{children}</ol>
              ),
              li: ({ children }) => (
                <li className="mb-2">{children}</li>
              ),
              table: ({ children }) => (
                <div className="overflow-x-auto mb-4">
                  <table className="w-full border-collapse">
                    {children}
                  </table>
                </div>
              ),
              th: ({ children }) => (
                <th className="border border-border bg-muted px-4 py-2 text-left font-medium">
                  {children}
                </th>
              ),
              td: ({ children }) => (
                <td className="border border-border px-4 py-2">
                  {children}
                </td>
              ),
              code: ({ className, children, ...props }) => {
                const isInline = !className
                if (isInline) {
                  return (
                    <code className="bg-muted px-1.5 py-0.5 rounded text-sm font-mono">
                      {children}
                    </code>
                  )
                }
                return (
                  <code className={cn('block bg-muted p-4 rounded-sm overflow-x-auto text-sm font-mono', className)} {...props}>
                    {children}
                  </code>
                )
              },
              pre: ({ children }) => (
                <pre className="bg-muted p-4 rounded-sm overflow-x-auto mb-4">
                  {children}
                </pre>
              ),
              blockquote: ({ children }) => (
                <blockquote className="border-l-4 border-primary/30 pl-4 italic my-4">
                  {children}
                </blockquote>
              ),
            }}
          >
            {section.content}
          </ReactMarkdown>
        )
      })}
    </div>
  )
}