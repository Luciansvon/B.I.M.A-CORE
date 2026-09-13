' ============================================================
' B.I.M.A Core - Windows AutoStart Launcher
' Menjalankan 9Router (jika belum aktif) dan membangkitkan PM2
' secara senyap di latar belakang saat login Windows.
' ============================================================

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

projectRoot = "C:\Users\shint\projects\BIMA_CORE"

' 1. Cek port 20128, nyalakan 9Router jika belum aktif
checkPortCmd = "powershell -WindowStyle Hidden -NoProfile -Command ""if (-not (Get-NetTCPConnection -LocalPort 20128 -ErrorAction SilentlyContinue)) { Start-Process '9router' -WindowStyle Hidden }"""
WshShell.Run checkPortCmd, 0, True

WScript.Sleep 2000

' 2. Jalankan PM2 start ecosystem.config.js secara senyap
pm2Cmd = "cmd /c cd /d """ & projectRoot & """ && pm2 start ecosystem.config.js"
WshShell.Run pm2Cmd, 0, False