import { useState, useCallback } from 'react'
import { Upload, X, FileSpreadsheet, AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { cn, formatBytes } from '@/lib/utils'
import type { UploadedFile } from '@/lib/types'

interface FileUploadProps {
  file: UploadedFile | null
  onFileChange: (file: UploadedFile | null) => void
  onUpload: (file: File) => Promise<void>
  isUploading: boolean
}

export function FileUpload({ file, onFileChange, onUpload, isUploading }: FileUploadProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const files = e.dataTransfer.files
    if (files.length > 0) {
      handleFile(files[0])
    }
  }, [])

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files && files.length > 0) {
      handleFile(files[0])
    }
  }, [])

  const handleFile = async (selectedFile: File) => {
    setError(null)

    const allowedExtensions = ['.xlsx', '.xls', '.csv']
    const fileExt = selectedFile.name.substring(selectedFile.name.lastIndexOf('.')).toLowerCase()

    if (!allowedExtensions.includes(fileExt)) {
      setError(`不支持的文件类型，仅支持: ${allowedExtensions.join(', ')}`)
      return
    }

    try {
      await onUpload(selectedFile)
    } catch (err) {
      setError(err instanceof Error ? err.message : '上传失败')
    }
  }

  const removeFile = () => {
    onFileChange(null)
    setError(null)
  }

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center gap-2">
          <FileSpreadsheet className="h-5 w-5 text-muted-foreground" />
          <CardTitle className="text-lg">数据文件</CardTitle>
        </div>
        <CardDescription>
          上传 Excel 或 CSV 格式的数据文件
        </CardDescription>
      </CardHeader>
      <CardContent>
        {file ? (
          <div className="animate-fade-in">
            <div className="flex items-center justify-between p-4 rounded-sm border border-border bg-muted/50">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-sm bg-primary/10 flex items-center justify-center">
                  <FileSpreadsheet className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <p className="font-medium">{file.original_name}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <Badge variant="secondary">{formatBytes(file.size)}</Badge>
                    {file.rows && (
                      <Badge variant="secondary">{file.rows} 行</Badge>
                    )}
                    {file.columns && (
                      <Badge variant="outline">{file.columns.length} 列</Badge>
                    )}
                  </div>
                </div>
              </div>
              <Button variant="ghost" size="icon" onClick={removeFile}>
                <X className="h-4 w-4" />
              </Button>
            </div>

            {file.columns && (
              <div className="mt-4">
                <p className="text-sm font-medium mb-2">数据列</p>
                <div className="flex flex-wrap gap-2">
                  {file.columns.map((col) => (
                    <Badge key={col} variant="outline">{col}</Badge>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div
            className={cn(
              "relative border-2 border-dashed rounded-sm p-8 transition-all duration-200",
              isDragging
                ? "border-primary bg-primary/5"
                : "border-border hover:border-primary/50",
              isUploading && "opacity-50 pointer-events-none"
            )}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <input
              type="file"
              accept=".xlsx,.xls,.csv"
              onChange={handleFileSelect}
              className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
              disabled={isUploading}
            />
            <div className="flex flex-col items-center text-center">
              <div className={cn(
                "h-12 w-12 rounded-full bg-muted flex items-center justify-center mb-4 transition-colors",
                isDragging && "bg-primary/20"
              )}>
                <Upload className={cn(
                  "h-5 w-5 text-muted-foreground transition-colors",
                  isDragging && "text-primary"
                )} />
              </div>
              <p className="font-medium mb-1">
                {isUploading ? '上传中...' : '拖放文件或点击上传'}
              </p>
              <p className="text-sm text-muted-foreground">
                支持 .xlsx, .xls, .csv 格式
              </p>
            </div>
          </div>
        )}

        {error && (
          <div className="mt-4 flex items-center gap-2 text-sm text-destructive">
            <AlertCircle className="h-4 w-4" />
            {error}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
