@echo off
REM 2026-03-27 Asia/Shanghai
REM 主要修改内容：在启动 LangGraph Dev 前自动切换到 py312_agent conda 环境

call conda activate py312_agent
if errorlevel 1 (
    echo [ERROR] conda activate py312_agent failed.
    exit /b %errorlevel%
)

langgraph dev --allow-blocking
