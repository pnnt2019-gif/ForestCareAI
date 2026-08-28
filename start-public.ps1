$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Start-Process powershell -ArgumentList '-NoExit', '-Command', "Set-Location '$projectRoot\backend'; .\venv\Scripts\python.exe app.py"
Start-Process powershell -ArgumentList '-NoExit', '-Command', "Set-Location '$projectRoot\frontend'; npm.cmd run dev -- --host 0.0.0.0"
Start-Process powershell -ArgumentList '-NoExit', '-Command', "& 'C:\Program Files (x86)\cloudflared\cloudflared.exe' tunnel --protocol http2 --edge-ip-version 4 --url http://127.0.0.1:5173"

Write-Host 'Da mo backend, frontend va Cloudflare Tunnel.'
Write-Host 'Mo terminal Cloudflare de copy URL trycloudflare.com de gui cho moi nguoi.'