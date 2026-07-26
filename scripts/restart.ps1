# DataReportNew 重启脚本
# 等同于先停止再启动

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $PSCommandPath

Write-Host "[i] 执行停止脚本..." -ForegroundColor Cyan
& "$scriptDir\stop.ps1"

Start-Sleep -Seconds 2

Write-Host "[i] 执行启动脚本..." -ForegroundColor Cyan
& "$scriptDir\start.ps1"