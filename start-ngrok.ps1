# Sobe o tunel ngrok (URL fixa) escondido. Chamado pela tarefa agendada no logon.
$ngrok = "C:\Users\natoa\AppData\Local\Microsoft\WinGet\Packages\Ngrok.Ngrok_Microsoft.Winget.Source_8wekyb3d8bbwe\ngrok.exe"
$url   = "https://oversold-starboard-elastic.ngrok-free.dev"
$port  = 8000

# espera Docker/backend subir antes de abrir o tunel
Start-Sleep -Seconds 30

# nao abre 2o tunel se ja tiver um rodando
try {
  $t = Invoke-RestMethod "http://127.0.0.1:4040/api/tunnels" -TimeoutSec 2
  if ($t.tunnels) { exit 0 }
} catch {}

Start-Process -FilePath $ngrok `
  -ArgumentList "http","--url=$url","$port" `
  -WindowStyle Hidden
