#requires -version 5.1
<#
.SYNOPSIS
    Instalador universal de Imrryr OS (Windows) — doble clic y listo.

.DESCRIPTION
    Pensado para instalarse en el computador de otra persona sin
    conocimientos técnicos: detecta qué falta (Python, Node.js, Bun,
    OpenCode) y lo instala solo, arma el entorno virtual de Python, instala
    las dependencias del proyecto y del sidecar de WhatsApp, y deja dos
    accesos directos en el Escritorio ("Iniciar Imrryr OS" / "Detener
    Imrryr OS") para no volver a tocar una terminal.

.USAGE
    Clic derecho sobre install.ps1 > "Ejecutar con PowerShell"
    (o desde una terminal: powershell -ExecutionPolicy Bypass -File install.ps1)
#>

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

function Write-Step {
    param([string]$Msg)
    Write-Host "[instalador] $Msg" -ForegroundColor Cyan
}

function Write-Warn2 {
    param([string]$Msg)
    Write-Host "[instalador] ADVERTENCIA: $Msg" -ForegroundColor Yellow
}

function Test-CommandExists {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Update-SessionPath {
    # Los instaladores (winget, bun, npm -g) escriben el PATH en el registro,
    # pero este proceso de PowerShell ya arrancó con el PATH viejo. Lo
    # recargamos para poder usar los binarios recién instalados sin abrir
    # una terminal nueva.
    $machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machinePath;$userPath"
}

function Install-WithWinget {
    param([string]$Id, [string]$NombreAmigable)
    if (-not (Test-CommandExists "winget")) {
        Write-Warn2 "winget no está disponible. Instala $NombreAmigable manualmente y vuelve a correr este script."
        return $false
    }
    Write-Step "Instalando $NombreAmigable vía winget..."
    winget install --id $Id --silent --accept-package-agreements --accept-source-agreements | Out-Null
    Update-SessionPath
    return $true
}

# ---------------------------------------------------------------------------
# 1. Python 3.10-3.13 (evitamos 3.14+: algunas dependencias como chromadb
#    todavía no tienen wheels precompilados para versiones tan nuevas, y
#    compilarlas desde código fuente falla sin un toolchain de Rust/C instalado)
# ---------------------------------------------------------------------------
Write-Step "Verificando Python..."
$PythonExe = $null

function Test-PythonCandidate {
    param([string]$Launcher, [string[]]$LauncherArgs)
    try {
        $verLine = & $Launcher @LauncherArgs -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if (-not $verLine) { return $null }
        $parts = $verLine.Split(".")
        if ([int]$parts[0] -eq 3 -and [int]$parts[1] -ge 10 -and [int]$parts[1] -le 13) {
            $exe = & $Launcher @LauncherArgs -c "import sys; print(sys.executable)" 2>$null
            return $exe
        }
    } catch {}
    return $null
}

# Preferir versiones específicas conocidas-buenas vía el "py launcher"
if (Test-CommandExists "py") {
    foreach ($ver in @("3.13", "3.12", "3.11", "3.10")) {
        $found = Test-PythonCandidate -Launcher "py" -LauncherArgs @("-$ver")
        if ($found) { $PythonExe = $found; break }
    }
}
# Si no hay "py launcher" o no encontró nada, probar "python" a secas
if (-not $PythonExe -and (Test-CommandExists "python")) {
    $PythonExe = Test-PythonCandidate -Launcher "python" -LauncherArgs @()
}

if ($PythonExe) {
    Write-Step "Usando Python: $PythonExe"
} else {
    Install-WithWinget -Id "Python.Python.3.11" -NombreAmigable "Python 3.11"
    if (Test-CommandExists "py") {
        $PythonExe = Test-PythonCandidate -Launcher "py" -LauncherArgs @("-3.11")
    }
    if (-not $PythonExe) {
        Write-Warn2 "No se pudo instalar/encontrar Python 3.10-3.13 automáticamente. Descárgalo de https://python.org (marca 'Add to PATH') y vuelve a correr install.ps1."
        exit 1
    }
}

# ---------------------------------------------------------------------------
# 2. Node.js (para OpenCode y el sidecar de WhatsApp)
# ---------------------------------------------------------------------------
Write-Step "Verificando Node.js..."
if (-not (Test-CommandExists "node")) {
    Install-WithWinget -Id "OpenJS.NodeJS.LTS" -NombreAmigable "Node.js"
    if (-not (Test-CommandExists "node")) {
        Write-Warn2 "No se pudo instalar Node.js automáticamente. Descárgalo de https://nodejs.org y vuelve a correr install.ps1."
        exit 1
    }
} else {
    Write-Step "Node.js $(node --version) encontrado."
}

# ---------------------------------------------------------------------------
# 3. Bun (requerido por OpenCode)
# ---------------------------------------------------------------------------
Write-Step "Verificando Bun..."
if (-not (Test-CommandExists "bun")) {
    Write-Step "Instalando Bun..."
    powershell -c "irm bun.sh/install.ps1 | iex" | Out-Null
    Update-SessionPath
    if (-not (Test-CommandExists "bun")) {
        Write-Warn2 "No se pudo instalar Bun automáticamente. Instálalo manualmente: https://bun.sh"
    }
} else {
    Write-Step "Bun $(bun --version) encontrado."
}

# ---------------------------------------------------------------------------
# 4. OpenCode (motor de agentes)
# ---------------------------------------------------------------------------
Write-Step "Verificando OpenCode..."
if (-not (Test-CommandExists "opencode")) {
    Write-Step "Instalando OpenCode (npm install -g opencode-ai)..."
    npm install -g opencode-ai | Out-Null
    Update-SessionPath
    if (-not (Test-CommandExists "opencode")) {
        Write-Warn2 "No se pudo instalar OpenCode automáticamente. Corre manualmente: npm install -g opencode-ai"
        exit 1
    }
} else {
    Write-Step "OpenCode encontrado."
}

# ---------------------------------------------------------------------------
# 5. Entorno virtual de Python + dependencias + base de datos
#    (reutiliza scripts/install.py, ya probado, en vez de duplicar su lógica)
# ---------------------------------------------------------------------------
Write-Step "Preparando el entorno de Imrryr OS (venv, dependencias, base de datos)..."
Push-Location $Root
try {
    & $PythonExe scripts\install.py
    if ($LASTEXITCODE -ne 0) {
        throw "scripts/install.py terminó con errores."
    }
} finally {
    Pop-Location
}

# ---------------------------------------------------------------------------
# 6. Dependencias del sidecar de WhatsApp (Node)
# ---------------------------------------------------------------------------
$SidecarDir = Join-Path $Root "gateway\whatsapp_local"
if (Test-Path $SidecarDir) {
    Write-Step "Instalando dependencias del sidecar de WhatsApp (npm install)..."
    Push-Location $SidecarDir
    try {
        npm install
    } finally {
        Pop-Location
    }
}

# ---------------------------------------------------------------------------
# 7. Accesos directos en el Escritorio
# ---------------------------------------------------------------------------
Write-Step "Creando accesos directos..."
$Desktop = [Environment]::GetFolderPath("Desktop")
$Shell = New-Object -ComObject WScript.Shell
$PythonExe = Join-Path $Root ".venv\Scripts\python.exe"

$Iniciar = $Shell.CreateShortcut((Join-Path $Desktop "Iniciar Imrryr OS.lnk"))
$Iniciar.TargetPath = $PythonExe
$Iniciar.Arguments = "scripts\startup.py"
$Iniciar.WorkingDirectory = $Root
$Iniciar.Description = "Levanta Imrryr OS completo y abre el dashboard"
$Iniciar.Save()

$Detener = $Shell.CreateShortcut((Join-Path $Desktop "Detener Imrryr OS.lnk"))
$Detener.TargetPath = $PythonExe
$Detener.Arguments = "scripts\shutdown.py"
$Detener.WorkingDirectory = $Root
$Detener.Description = "Detiene todos los servicios de Imrryr OS"
$Detener.Save()

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  Imrryr OS instalado." -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Proximo paso: edita config\.env y agrega tu GEMINI_API_KEY"
Write-Host "  (o la API key del proveedor de IA que prefieras usar)."
Write-Host ""
Write-Host "  Despues, usa el acceso directo 'Iniciar Imrryr OS' del Escritorio."
Write-Host ""
