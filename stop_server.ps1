$conn = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1
if (-not $conn) { exit 0 }
try {
    $page = (Invoke-WebRequest 'http://127.0.0.1:8765/' -UseBasicParsing -TimeoutSec 2).Content
} catch {
    exit 2
}
if ($page -notmatch 'id="scanBtn"') { exit 2 }
Stop-Process -Id $conn.OwningProcess -Force
