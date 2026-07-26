@echo off
chcp 65001 > nul
REM DataReportNew 停止脚本 (CMD 版本)

setlocal

echo.
echo ========================================
echo    DataReportNew 停止脚本
echo ========================================
echo.

echo [i] 停止占用端口 8000 的进程...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000"') do (
    taskkill /F /PID %%a > nul 2>&1
    echo   已停止 PID: %%a
)

echo [i] 停止占用端口 5173 的进程...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173"') do (
    taskkill /F /PID %%a > nul 2>&1
    echo   已停止 PID: %%a
)

REM 清理可能的进程
echo [i] 清理相关进程...
taskkill /F /IM node.exe /FI "WINDOWTITLE eq DataReport*" > nul 2>&1

echo.
echo ========================================
echo    所有服务已停止
echo ========================================
echo.
pause