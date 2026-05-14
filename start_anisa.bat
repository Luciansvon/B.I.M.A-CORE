@echo off
title Membangunkan Sistem Anisa...

echo [1/2] Menyalakan B.I.M.A Core di WSL...
echo        (Dashboard modern auto-start di port 8000)
wsl -d Ubuntu -e bash -ic "cd /home/bima_lucian/BIMA_CORE && pm2 restart ANISA || pm2 start ecosystem.config.js"

echo [2/2] Memanggil Anisa Desktop Pet...
start "Anisa Pet" python \\wsl.localhost\Ubuntu\home\bima_lucian\BIMA_CORE\frontend\anisa_pet_frontend.py

echo.
echo ============================================
echo   Semua sistem aktif!
echo   Dashboard: http://localhost:8000/dashboard
echo   Metrics:   http://localhost:8000/api/metrics
echo   Pet: Lihat di Desktop
echo ============================================
pause
