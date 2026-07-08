@echo off
title Stratum — AI Trading Strategy Analyzer
cd /d "%~dp0stratum"
start /b pythonw app.py
echo Stratum launched (running in background without terminal window).
echo Close the application window to exit.
echo.
