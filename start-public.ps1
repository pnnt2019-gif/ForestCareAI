$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

$backendPattern = [regex]::Escape("$projectRoot\backend")
$frontendPattern = [regex]::Escape("$projectRoot\frontend")

$existing = Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -match $backendPattern -or
        $_.CommandLine -match $frontendPattern -or
        $_.CommandLine -match 'python.exe app.py' -or
        $_.CommandLine -match 'vite --host 0.0.0.0' -or
        $_.CommandLine -match 'vite --host 0.0.0.0 --port 4173'
    } |
    Select-Object -ExpandProperty ProcessId

if ($existing) {
    foreach ($pid in $existing | Sort-Object -Unique) {
        try {
            Stop-Process -Id $pid -Force -ErrorAction Stop
            Write-Host "Stopped stale app process: $pid"
        } catch {
            Write-Host "Could not stop process $pid - already exited."
        }
    }
}

Start-Process powershell -ArgumentList '-NoExit', '-Command', "Set-Location '$projectRoot\backend'; .\venv\Scripts\python.exe app.py"
Start-Process powershell -ArgumentList '-NoExit', '-Command', "Set-Location '$projectRoot\frontend'; npm.cmd run dev -- --host 0.0.0.0 --port 4173 --strictPort"
Start-Process powershell -ArgumentList '-NoExit', '-Command', "& 'C:\Program Files (x86)\cloudflared\cloudflared.exe' tunnel --protocol http2 --edge-ip-version 4 --url http://127.0.0.1:4173"

Write-Host 'Da mo backend, frontend va Cloudflare Tunnel.'
Write-Host 'Port backend: http://127.0.0.1:5000'
Write-Host 'Port frontend: http://127.0.0.1:4173'
Write-Host 'Mo terminal Cloudflare de copy URL trycloudflare.com de gui cho moi nguoi.'