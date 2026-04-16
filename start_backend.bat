@echo off
REM 2026-04-16 Asia/Shanghai
REM Main change: start FastAPI backend through the Python launcher so Windows uses SelectorEventLoop before Uvicorn boot.
REM 2026-04-16 Asia/Shanghai
REM Additional change: disable reload by default on Windows because Uvicorn WatchFiles spawns a child process that won't inherit the SelectorEventLoop policy.

call conda activate py312_agent
if errorlevel 1 (
    echo [ERROR] conda activate py312_agent failed.
    exit /b %errorlevel%
)

python run_backend.py
