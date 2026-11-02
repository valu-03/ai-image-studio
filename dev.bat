@echo off
cd /d %~dp0
start "AI Image Studio API" python -m uvicorn studio.server:dev_app --factory --reload --port 8790
start "AI Image Studio Web" cmd /k npm --prefix web run dev -- --port 5178
