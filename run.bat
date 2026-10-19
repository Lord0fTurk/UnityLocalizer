@echo off
title UnityLocalizer
chcp 65001 > nul
python run.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo UnityLocalizer crashed or failed to start with code %ERRORLEVEL%.
    pause
)
