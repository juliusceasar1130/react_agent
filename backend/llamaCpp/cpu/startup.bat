@echo off
setlocal

REM Updated: 2026-03-23 Asia/Shanghai
REM Main changes:
REM 1. Add llama.cpp CPU startup script for Qwen3 embedding
REM 2. Fix Windows cmd encoding issues by keeping this file ASCII-only
REM 3. Keep conservative params for stable local startup

REM =========================
REM Basic config
REM =========================

REM Directory containing llama-server.exe
set "LLAMA_DIR=F:\300_llamacpp\llama-b8480-bin-win-cpu-x64"

REM Listen on localhost only
set "HOST=127.0.0.1"

REM Embedding service port
set "PORT=8081"

REM Hugging Face GGUF model spec
set "MODEL_SPEC=Qwen/Qwen3-Embedding-0.6B-GGUF:q8_0"

REM =========================
REM Param notes
REM =========================

REM --embedding
REM   Enable embedding mode and return vectors instead of generated text.

REM --pooling last
REM   Qwen3 Embedding should use last-token pooling.

REM --ctx-size 2048
REM   Smaller context size reduces RAM usage and avoids allocation failures.

REM --parallel 1
REM   Low concurrency local use. Safer and lighter on memory.

REM --batch-size 128
REM   Batch size. Larger values may improve throughput but use more RAM.

REM --ubatch-size 128
REM   Micro-batch size. Keep conservative to avoid startup failure.

REM --host / --port
REM   Bind the server to localhost:8081 only.

echo Starting llama.cpp embedding server...
echo Model: %MODEL_SPEC%
echo URL:   http://%HOST%:%PORT%
echo.

cd /d "%LLAMA_DIR%"
if errorlevel 1 (
  echo Failed to enter LLAMA_DIR: %LLAMA_DIR%
  pause
  exit /b 1
)

llama-server.exe ^
  -hf "%MODEL_SPEC%" ^
  --embedding ^
  --pooling last ^
  --host "%HOST%" ^
  --port "%PORT%" ^
  --ctx-size 2048 ^
  --parallel 1 ^
  --batch-size 128 ^
  --ubatch-size 128

echo.
echo llama-server exited.
pause
