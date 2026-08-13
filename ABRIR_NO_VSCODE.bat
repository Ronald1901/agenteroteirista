@echo off
cd /d "%~dp0"
where code >nul 2>nul
if errorlevel 1 (
  echo VS Code CLI nao encontrado. Abra esta pasta manualmente no VS Code.
  pause
  exit /b 1
)
code .
