# Sobe o tunel ngrok (URL fixa) escondido. Chamado pela tarefa de Inicializacao no logon.
#
# Configure antes de usar (uma vez, no seu usuario do Windows):
#   [Environment]::SetEnvironmentVariable("PRONUNCIA_NGROK_URL", "https://SEU-DOMINIO.ngrok-free.dev", "User")
#   [Environment]::SetEnvironmentVariable("PRONUNCIA_NGROK_BIN", "C:\caminho\para\ngrok.exe", "User")
# O binario tambem e encontrado automaticamente se o ngrok estiver no PATH.

$url = $env:PRONUNCIA_NGROK_URL
if (-not $url) {
  Write-Error "PRONUNCIA_NGROK_URL nao definida. Veja o cabecalho deste script."
  exit 1
}

$ngrok = $env:PRONUNCIA_NGROK_BIN
if (-not $ngrok) {
  $cmd = Get-Command ngrok -ErrorAction SilentlyContinue
  if ($cmd) { $ngrok = $cmd.Source }
}
if (-not $ngrok -or -not (Test-Path $ngrok)) {
  Write-Error "ngrok.exe nao encontrado. Defina PRONUNCIA_NGROK_BIN ou ponha o ngrok no PATH."
  exit 1
}

$port = 8000

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
