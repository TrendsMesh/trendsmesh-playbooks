@echo off
rem Runs tm through bootstrap\tm.ps1 with -ExecutionPolicy Bypass. tm.ps1 is kept out of bin\,
rem so PowerShell never resolves "tm" to a script that its execution policy would refuse.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\bootstrap\tm.ps1" %*
exit /b %ERRORLEVEL%
