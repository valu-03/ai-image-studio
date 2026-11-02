@echo off
cd /d %~dp0
rem Install web dependencies once; rebuild the UI on every launch so it never goes stale.
if not exist web\node_modules (
  call npm --prefix web ci || exit /b 1
)
call npm --prefix web run build || exit /b 1
python -m studio.desktop
