# PowerShell Stopping Script
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    # 정상 종료 시 창이 자동으로 닫히도록 -NoExit 제거
    Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs -Wait
    exit
}

try {
    $root = Split-Path -Parent $PSCommandPath
    Set-Location $root

    Write-Host "[*] Shutting down system..."

    # 특정 패턴 및 키워드로 프로세스 트리 전체 종료 함수 정의
    function Kill-ProcessTree($pattern) {
        $procs = Get-CimInstance Win32_Process | Where-Object {$_.CommandLine -like "*$pattern*"}
        foreach ($p in $procs) {
            # taskkill /T /F를 사용하여 부모/자식 관계를 모두 정리 (콘솔창 포함)
            taskkill /F /T /PID $p.ProcessId 2>$null
        }
    }

    Write-Host "[*] Stopping Kiwoom Gateway (32-bit) & Consoles..."
    Kill-ProcessTree "kiwoom.api_server"
    Kill-ProcessTree "run_kiwoom_admin"

    Write-Host "[*] Stopping Strategy Engine (64-bit) & Consoles..."
    Kill-ProcessTree "backend.main"
    Kill-ProcessTree "Strategy Engine (64-bit)"

    Write-Host "[*] Stopping Vue Frontend & Consoles..."
    # 1) Port-based kill
    $conn = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue
    if ($conn) { taskkill /F /T /PID $conn.OwningProcess 2>$null }

    # 2) CommandLine pattern kill
    Kill-ProcessTree "start_with_title"
    Kill-ProcessTree "vite"
    Kill-ProcessTree "start_vue"
    Kill-ProcessTree "Vue Frontend"

    # 3) PID file kill
    $pidPath = Join-Path $root "frontend\vue_frontend.pid"
    if (Test-Path $pidPath) {
        $targetPid = Get-Content $pidPath | Out-String
        if ($targetPid -match '^\d+$') {
            taskkill /F /T /PID $targetPid.Trim() 2>$null
        }
        Remove-Item $pidPath -Force -ErrorAction SilentlyContinue
        Write-Host "[*] Killed Vue Frontend (via PID file)"
    }

    Write-Host "`n[*] All processes and console windows stopped."
    Start-Sleep -Seconds 2
}
catch {
    Write-Error "An error occurred during shutdown: $_"
    # 오류 발생 시 창이 바로 닫히지 않도록 키 입력을 기다립니다.
    Read-Host "`n오류가 발생했습니다. 확인 후 Enter를 누르면 창이 닫힙니다."
}
