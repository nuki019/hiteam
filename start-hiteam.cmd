@echo off
setlocal

set "PROJECT_DIR=%~dp0"
set "HITTEAM_URL=http://127.0.0.1:8765/index.html"

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$project=[System.IO.Path]::GetFullPath($env:PROJECT_DIR); $url=$env:HITTEAM_URL; $port=8765; $listener=Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue; if(-not $listener){$pyLauncher=Get-Command py.exe -ErrorAction SilentlyContinue; $python=Get-Command python.exe -ErrorAction SilentlyContinue; if($pyLauncher){$file=$pyLauncher.Source; $args=@('-3','-m','http.server',$port,'--bind','127.0.0.1')}elseif($python){$file=$python.Source; $args=@('-m','http.server',$port,'--bind','127.0.0.1')}else{Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('Python 3 is required.','HiTeam startup failed')|Out-Null; exit 1}; Start-Process -WindowStyle Hidden -FilePath $file -ArgumentList $args -WorkingDirectory $project}; for($i=0;$i -lt 30;$i++){if(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue){break}; Start-Sleep -Milliseconds 100}; if(-not(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)){Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('HiTeam server failed to start. Check port 8765.','HiTeam startup failed')|Out-Null; exit 1}; Start-Process $url"

exit /b 0
