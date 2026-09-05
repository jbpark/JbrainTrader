# PowerShell Running Script
$root = Split-Path -Parent $PSCommandPath
Set-Location $root

Write-Host "[*] Starting Kiwoom Gateway (32-bit)..."
$python32 = "C:\Program Files (x86)\Python311-32\python.exe"
$env:PYTHONPATH = $root
Start-Process -FilePath "cmd.exe" -ArgumentList "/c `"$root\run_kiwoom_admin.bat`"" -WindowStyle Normal

Write-Host "[*] Starting Strategy Engine (64-bit)..."
$python64 = "C:\ProgramData\anaconda3\python.exe"
# Start-Process doesn't have a -Title parameter. We use 'title' command via cmd /k.
Start-Process -FilePath "cmd.exe" -ArgumentList "/k title Strategy Engine (64-bit) & `"$python64`" -m backend.main" -WindowStyle Normal

Write-Host "[*] Starting Vue Frontend..."
Set-Location "$root\frontend"
# start_vue.bat already sets its title internally.
$p = Start-Process -FilePath "cmd.exe" -ArgumentList "/k start_vue.bat" -PassThru -WindowStyle Normal
$p.Id | Out-File -FilePath "$root\frontend\vue_frontend.pid" -Encoding Ascii -NoNewline

Write-Host "`n[*] System is starting up."
Write-Host "[*] Please accept the UAC prompt for Kiwoom Gateway if it appears."
Start-Sleep -Seconds 1
