@echo off
REM Windows CMD wrapper — same targets as Makefile
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0make.ps1" %*
