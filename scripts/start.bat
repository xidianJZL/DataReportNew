@echo off
chcp 65001 > nul
REM DataReportNew 启动脚本 (CMD 版本)

setlocal

set "PROJECT_ROOT=%~dp0.."
cd /d "%PROJECT_ROOT%"

set "CONDA_PATH=D:\DailySoft\AI\tool\miniconda3\condabin"
set "CONDA_ENV=AItool"

echo.
echo ========================================
echo    DataReportNew 启动脚本
echo ========================================
echo.

REM 检查 conda
if not exist "%CONDA_PATH%\conda.bat" (
    echo [X] 未找到 conda: %CONDA_PATH%\conda.bat
    pause
    exit /b 1
)
echo [OK] 找到 Conda: %CONDA_PATH%

REM 检查/创建虚拟环境
echo [i] 检查虚拟环境 %CONDA_ENV%...
call "%CONDA_PATH%\conda.bat" env list | findstr /C:"%CONDA_ENV%" > nul
if errorlevel 1 (
    echo [!] 虚拟环境不存在，正在创建...
    call "%CONDA_PATH%\conda.bat" create -n "%CONDA_ENV%" python=3.11 -y
    if errorlevel 1 (
        echo [X] 创建虚拟环境失败
        pause
        exit /b 1
    )
)
echo [OK] 虚拟环境已就绪

REM 安装后端依赖
echo [i] 检查后端依赖...
call "%CONDA_PATH%\conda.bat" run -n "%CONDA_ENV%" pip install -r "%PROJECT_ROOT%\backend\requirements.txt" --quiet
if errorlevel 1 (
    echo [X] 后端依赖安装失败
    pause
    exit /b 1
)
echo [OK] 后端依赖已就绪

REM 检查前端依赖
echo [i] 检查前端依赖...
if not exist "%PROJECT_ROOT%\frontend\node_modules" (
    echo [i] 首次运行，正在安装前端依赖...
    cd /d "%PROJECT_ROOT%\frontend"
    call npm install --silent
    if errorlevel 1 (
        echo [X] 前端依赖安装失败
        pause
        exit /b 1
    )
    cd /d "%PROJECT_ROOT%"
)
echo [OK] 前端依赖已就绪

REM 创建日志目录
if not exist "%PROJECT_ROOT%\logs" mkdir "%PROJECT_ROOT%\logs"

REM 启动后端
echo [i] 启动后端服务...
start /min "DataReport-Backend" cmd /c "cd /d %PROJECT_ROOT% && call %CONDA_PATH%\conda.bat run -n %CONDA_ENV% python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload > %PROJECT_ROOT%\logs\backend.log 2>&1"

REM 等待后端启动
echo [i] 等待后端服务启动...
timeout /t 5 /nobreak > nul

REM 启动前端
echo [i] 启动前端服务...
start /min "DataReport-Frontend" cmd /c "cd /d %PROJECT_ROOT%\frontend && npm run dev > %PROJECT_ROOT%\logs\frontend.log 2>&1"

REM 等待前端启动
echo [i] 等待前端服务启动...
timeout /t 8 /nobreak > nul

echo.
echo ========================================
echo    服务已启动！
echo ========================================
echo.
echo   前端地址: http://localhost:5173
echo   后端 API: http://localhost:8000
echo   API 文档: http://localhost:8000/docs
echo.
echo   使用 scripts\stop.bat 停止服务
echo.
pause