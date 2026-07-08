#!/usr/bin/env bash
# install.sh — Instalador universal de Imrryr OS (macOS / Linux)
# ==================================================================
# Equivalente a install.ps1 (Windows): detecta qué falta (Python, Node.js,
# Bun, OpenCode) y lo instala solo, arma el entorno virtual de Python,
# instala las dependencias del proyecto y del sidecar de WhatsApp, y deja
# lanzadores de doble clic para iniciar/detener el sistema.
#
# Uso:
#   chmod +x install.sh && ./install.sh
#
# Nota: no se pudo probar en vivo en esta sesión (se desarrolló en Windows);
# revisado contra la documentación oficial de cada instalador. Si algo falla
# en tu distribución, instala manualmente el prerrequisito que falte y vuelve
# a correr el script — es idempotente, salta lo que ya esté instalado.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

step() { echo "[instalador] $1"; }
warn() { echo "[instalador] ADVERTENCIA: $1" >&2; }
has_cmd() { command -v "$1" >/dev/null 2>&1; }

OS="$(uname -s)"

# ---------------------------------------------------------------------------
# 1. Python 3.10-3.13 (evitamos 3.14+: algunas dependencias como chromadb
#    todavía no tienen wheels precompilados para versiones tan nuevas, y
#    compilarlas desde código fuente falla sin un toolchain de Rust/C instalado)
# ---------------------------------------------------------------------------
step "Verificando Python..."
PYTHON_BIN=""
for cand in python3.13 python3.12 python3.11 python3.10 python3; do
    if has_cmd "$cand"; then
        PY_VER="$("$cand" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)"
        [ -z "$PY_VER" ] && continue
        PY_MAJOR="${PY_VER%%.*}"
        PY_MINOR="${PY_VER##*.}"
        if [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -ge 10 ] && [ "$PY_MINOR" -le 13 ]; then
            PYTHON_BIN="$cand"
            step "Usando $cand (Python $PY_VER)."
            break
        fi
    fi
done
if [ -z "$PYTHON_BIN" ]; then
    step "Instalando Python 3.11..."
    if [ "$OS" = "Darwin" ] && has_cmd brew; then
        brew install python@3.11
        PYTHON_BIN="python3.11"
    elif has_cmd apt-get; then
        sudo apt-get update && sudo apt-get install -y python3.11 python3.11-venv
        PYTHON_BIN="python3.11"
    else
        warn "No se pudo instalar Python automáticamente. Instálalo manualmente (https://python.org, versión 3.10 a 3.13) y vuelve a correr install.sh."
        exit 1
    fi
fi

# ---------------------------------------------------------------------------
# 2. Node.js (para OpenCode y el sidecar de WhatsApp)
# ---------------------------------------------------------------------------
step "Verificando Node.js..."
if ! has_cmd node; then
    step "Instalando Node.js..."
    if [ "$OS" = "Darwin" ] && has_cmd brew; then
        brew install node
    elif has_cmd apt-get; then
        curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
        sudo apt-get install -y nodejs
    else
        warn "No se pudo instalar Node.js automáticamente. Instálalo manualmente (https://nodejs.org) y vuelve a correr install.sh."
        exit 1
    fi
else
    step "Node.js $(node --version) encontrado."
fi

# ---------------------------------------------------------------------------
# 3. Bun (requerido por OpenCode)
# ---------------------------------------------------------------------------
step "Verificando Bun..."
if ! has_cmd bun; then
    step "Instalando Bun..."
    curl -fsSL https://bun.sh/install | bash
    export PATH="$HOME/.bun/bin:$PATH"
else
    step "Bun $(bun --version) encontrado."
fi

# ---------------------------------------------------------------------------
# 4. OpenCode (motor de agentes)
# ---------------------------------------------------------------------------
step "Verificando OpenCode..."
if ! has_cmd opencode; then
    step "Instalando OpenCode (npm install -g opencode-ai)..."
    npm install -g opencode-ai
else
    step "OpenCode encontrado."
fi

# ---------------------------------------------------------------------------
# 5. Entorno virtual de Python + dependencias + base de datos
#    (reutiliza scripts/install.py, ya probado, en vez de duplicar su lógica)
# ---------------------------------------------------------------------------
step "Preparando el entorno de Imrryr OS (venv, dependencias, base de datos)..."
(cd "$ROOT" && "$PYTHON_BIN" scripts/install.py)

# ---------------------------------------------------------------------------
# 6. Dependencias del sidecar de WhatsApp (Node)
# ---------------------------------------------------------------------------
if [ -d "$ROOT/gateway/whatsapp_local" ]; then
    step "Instalando dependencias del sidecar de WhatsApp (npm install)..."
    (cd "$ROOT/gateway/whatsapp_local" && npm install)
fi

# ---------------------------------------------------------------------------
# 7. Lanzadores de doble clic en el Escritorio
# ---------------------------------------------------------------------------
step "Creando lanzadores..."
DESKTOP="$HOME/Desktop"
mkdir -p "$DESKTOP"
PYTHON_VENV="$ROOT/.venv/bin/python"

cat > "$DESKTOP/Iniciar Imrryr OS.command" <<EOF
#!/usr/bin/env bash
cd "$ROOT"
"$PYTHON_VENV" scripts/startup.py
EOF
chmod +x "$DESKTOP/Iniciar Imrryr OS.command"

cat > "$DESKTOP/Detener Imrryr OS.command" <<EOF
#!/usr/bin/env bash
cd "$ROOT"
"$PYTHON_VENV" scripts/shutdown.py
read -p "Presiona Enter para cerrar..."
EOF
chmod +x "$DESKTOP/Detener Imrryr OS.command"

if [ "$OS" = "Linux" ] && [ -n "${XDG_CURRENT_DESKTOP:-}" ]; then
    # .desktop además de .command, para entornos Linux con lanzador gráfico
    cat > "$DESKTOP/Iniciar Imrryr OS.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Iniciar Imrryr OS
Exec="$DESKTOP/Iniciar Imrryr OS.command"
Terminal=true
EOF
    chmod +x "$DESKTOP/Iniciar Imrryr OS.desktop"
fi

echo ""
echo "============================================================"
echo "  Imrryr OS instalado."
echo "============================================================"
echo ""
echo "  Proximo paso: edita config/.env y agrega tu GEMINI_API_KEY"
echo "  (o la API key del proveedor de IA que prefieras usar)."
echo ""
echo "  Despues, usa 'Iniciar Imrryr OS.command' en el Escritorio"
echo "  (en macOS, la primera vez puede pedirte permiso en"
echo "  Preferencias del Sistema > Seguridad para ejecutarlo)."
echo ""
