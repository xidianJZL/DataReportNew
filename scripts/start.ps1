# DataReportNew 启动脚本
# 自动激活 conda AItool 虚拟环境并启动前后端服务

$ErrorActionPreference = "Stop"

# 项目根目录
$PROJECT_ROOT = Split-Path -Parent $PSScriptRoot
Set-Location $PROJECT_ROOT

# Conda 路径
$CONDA_PATH = "D:\DailySoft\AI\tool\miniconda3\condabin"
$CONDA_ENV = "AItool"

# 颜色输出函数
function Write-Success { param($msg) Write-Host "[✓] $msg" -ForegroundColor Green }
function Write-Info { param($msg) Write-Host "[i] $msg" -ForegroundColor Cyan }
function Write-Warn { param($msg) Write-Host "[!] $msg" -ForegroundColor Yellow }
function Write-Err { param($msg) Write-Host "[✗] $msg" -ForegroundColor Red }

Write-Host ""
Write-Host "========================================" -ForegroundColor White
Write-Host "   DataReportNew 启动脚本" -ForegroundColor White
Write-Host "========================================" -ForegroundColor White
Write-Host ""

# 检查 conda
if (-not (Test-Path "$CONDA_PATH\conda.bat")) {
    Write-Err "未找到 conda: $CONDA_PATH\conda.bat"
    Write-Err "请检查 Conda 路径是否正确"
    exit 1
}
Write-Success "找到 Conda: $CONDA_PATH"

# 初始化 conda
Write-Info "初始化 Conda 环境..."
& "$CONDA_PATH\conda.bat" activate "$CONDA_ENV" 2>&1 | Out-Null

# 检查虚拟环境是否存在
$envInfo = & "$CONDA_PATH\conda.bat" env list 2>&1 | Out-String
if ($envInfo -notmatch "$CONDA_ENV") {
    Write-Warn "虚拟环境 $CONDA_ENV 不存在，正在创建..."
    & "$CONDA_PATH\conda.bat" create -n "$CONDA_ENV" python=3.11 -y
    if ($LASTEXITCODE -ne 0) {
        Write-Err "创建虚拟环境失败"
        exit 1
    }
}
Write-Success "虚拟环境 $CONDA_ENV 已就绪"

# 创建日志目录
$LOG_DIR = Join-Path $PROJECT_ROOT "logs"
if (-not (Test-Path $LOG_DIR)) {
    New-Item -ItemType Directory -Path $LOG_DIR | Out-Null
}

# 后端目录
$BACKEND_DIR = Join-Path $PROJECT_ROOT "backend"
$FRONTEND_DIR = Join-Path $PROJECT_ROOT "frontend"

# 安装后端依赖
Write-Info "检查后端依赖..."
& "$CONDA_PATH\conda.bat" run -n "$CONDA_ENV" --no-capture-output pip install -r "$BACKEND_DIR\requirements.txt" --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Err "后端依赖安装失败"
    exit 1
}
Write-Success "后端依赖已就绪"

# 检查并安装前端依赖
Write-Info "检查前端依赖..."
if (-not (Test-Path "$FRONTEND_DIR\node_modules")) {
    Write-Info "首次运行，正在安装前端依赖（可能需要几分钟）..."
    Push-Location $FRONTEND_DIR
    npm install --silent
    Pop-Location
    if ($LASTEXITCODE -ne 0) {
        Write-Err "前端依赖安装失败"
        exit 1
    }
}
Write-Success "前端依赖已就绪"

# 启动后端服务
Write-Info "启动后端服务 (端口 8000)..."
$backendLog = Join-Path $LOG_DIR "backend.log"
# 从项目根目录启动，使用 python -m backend.app 让相对导入正常工作
# 用单引号字符串 + -f 避免引号嵌套导致 && 被 PowerShell 解析
$backendCmd = 'cd /d "{0}" && set NO_PROXY=127.0.0.1,localhost && "{1}\conda.bat" run -n {2} --no-capture-output python -c "import sys,os; sys.stderr.write(f''UVICORN_RUNNING_IN: {{sys.executable}}\nUVICORN_ENV_PREFIX: {{sys.prefix}}\n''); sys.stderr.flush()" && "{1}\conda.bat" run -n {2} --no-capture-output python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload --reload-dir backend >> "{3}" 2>&1' -f $PROJECT_ROOT, $CONDA_PATH, $CONDA_ENV, $backendLog

Start-Process cmd -ArgumentList "/c", $backendCmd -WindowStyle Hidden

# 等待后端启动
Write-Info "等待后端服务启动..."
$maxWait = 30
$waited = 0
while ($waited -lt $maxWait) {
    Start-Sleep -Seconds 1
    $waited++
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            break
        }
    } catch {
        # 继续等待
    }
}

if ($waited -ge $maxWait) {
    Write-Warn "后端服务启动超时，请检查日志: $backendLog"
} else {
    Write-Success "后端服务已启动: http://localhost:8000"
}

# 启动前端服务
Write-Info "启动前端服务 (端口 5173)..."
$frontendLog = Join-Path $LOG_DIR "frontend.log"
$frontendCmd = 'cd /d "{0}" && npm run dev > "{1}" 2>&1' -f $FRONTEND_DIR, $frontendLog

Start-Process cmd -ArgumentList "/c", $frontendCmd -WindowStyle Hidden

# 等待前端启动
Write-Info "等待前端服务启动..."
$maxWait = 30
$waited = 0
while ($waited -lt $maxWait) {
    Start-Sleep -Seconds 1
    $waited++
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:5173" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            break
        }
    } catch {
        # 继续等待
    }
}

if ($waited -ge $maxWait) {
    Write-Warn "前端服务启动超时，请检查日志: $frontendLog"
} else {
    Write-Success "前端服务已启动: http://localhost:5173"
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "   服务已启动！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  前端地址: " -NoNewline; Write-Host "http://localhost:5173" -ForegroundColor Cyan
Write-Host "  后端 API: " -NoNewline; Write-Host "http://localhost:8000" -ForegroundColor Cyan
Write-Host "  API 文档: " -NoNewline; Write-Host "http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "  日志目录: $LOG_DIR" -ForegroundColor Gray
Write-Host ""
Write-Host "  使用 scripts\stop.ps1 停止服务" -ForegroundColor Yellow
Write-Host ""