@echo off
set USERNAME=%1
set PASSWORD=%2

echo [Renew IP] Current IP:
curl ifconfig.me
echo.

:: 1. MATIKAN FORTICLIENT
echo [Renew IP] Killing FortiClient processes...
taskkill /IM FortiClient.exe /F
taskkill /IM FortiSSLVPNclient.exe /F
taskkill /IM FortiTray.exe /F

:: 2. RESET WIFI (PENTING: Ini yang mengubah IP Publik Asli)
echo [Renew IP] Resetting WiFi Adapter...
netsh wlan disconnect
timeout /t 3 /nobreak > nul
netsh wlan connect
echo [Renew IP] Waiting for WiFi (10s)...
timeout /t 10 /nobreak > nul

:: 3. NYALAKAN ULANG FORTICLIENT
echo [Renew IP] Starting FortiClient...
:: Sesuaikan path ini jika perlu
start "" "C:\Program Files\Fortinet\FortiClient\FortiClient.exe"

:: Alternatif: Coba connect langsung via CLI jika command ini jalan
:: "C:\Program Files\Fortinet\FortiClient\FortiSSLVPNclient.exe" connect -h aksesu.bps.go.id:443 -u %USERNAME%:%PASSWORD%

echo [Renew IP] Waiting for VPN connection (manual/auto)...
timeout /t 15 /nobreak > nul

echo [Renew IP] New IP:
curl ifconfig.me
echo.

exit /b 0
