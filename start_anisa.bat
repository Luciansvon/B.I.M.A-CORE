@echo off
title Membangunkan Sistem Anisa...

echo [1/2] Menyalakan B.I.M.A Core di Windows...
echo        (Dashboard modern auto-start di port 8000)
cd /d "%~dp0"
call pm2 restart ecosystem.config.js || call pm2 start ecosystem.config.js

echo [2/2] Memanggil Anisa Desktop Pet...
if exist "frontend\anisa_pet_frontend.py" (
    start "Anisa Pet" bima_env\Scripts\python.exe frontend\anisa_pet_frontend.py
)

echo.
echo ============================================
echo   Semua sistem aktif!
echo   Dashboard: http://localhost:8000/dashboard
echo   Metrics:   http://localhost:8000/api/metrics
echo   Pet: Lihat di Desktop
echo ============================================
pause
