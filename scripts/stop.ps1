# DataReportNew 停止脚本
# 停止前后端服务

$ErrorActionPreference = "Stop"

# 颜色输出
function Write-Success { param($msg) Write-Host "[✓] $msg" -ForegroundColor Green }
function Write-Info { param($msg) Write-Host "[i] $msg" -ForegroundColor Cyan }

Write-Host ""
Write-Host "========================================" -ForegroundColor White
Write-Host "   DataReportNew 停止脚本" -ForegroundColor White
Write-Host "========================================" -ForegroundColor White
Write-Host ""

# 停止占用端口的进程
function Stop-ProcessOnPort {
    param([int]$Port)
    Write-Info "停止占用端口 $Port 的进程..."

    # 只取 LISTENING 状态的进程 (避免 TIME_WAIT/ESTABLISHED 误中)
    $procIds = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique

    foreach ($procId in $procIds) {
        if (-not $procId -or $procId -le 0) { continue }
        try {
            $process = Get-Process -Id $procId -ErrorAction Stop
            Write-Info "停止进程: $($process.ProcessName) (PID: $procId)"
            Stop-Process -Id $procId -Force -ErrorAction Stop
            Write-Success "已停止 $procId"
        } catch {
            # 进程可能已经退出
        }
    }
}

# 停止后端
Stop-ProcessOnPort -Port 8000

# 停止前端
Stop-ProcessOnPort -Port 5173

# 额外清理: 用 PID 扫描端口(LISTENING)找出遗漏的 uvicorn/vite
Write-Info "扫描端口确认清理..."
Stop-ProcessOnPort -Port 8000
Stop-ProcessOnPort -Port 5173

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "   所有服务已停止" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""