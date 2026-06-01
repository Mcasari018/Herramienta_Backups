#!/usr/bin/env bash
# ============================================================
#  Antigravity Backup — Instalador para Ubuntu/Debian Server
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_MIN="3.9"

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║     ANTIGRAVITY BACKUP — Instalador Linux        ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── Verificar Python ─────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "[!] Python3 no encontrado. Instalando..."
    sudo apt-get update -qq
    sudo apt-get install -y python3 python3-pip python3-venv
fi

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "[✓] Python $PY_VER detectado"

# ── Crear entorno virtual ─────────────────────────────────────
echo "[→] Creando entorno virtual en $SCRIPT_DIR/venv ..."
python3 -m venv "$SCRIPT_DIR/venv"
source "$SCRIPT_DIR/venv/bin/activate"

# ── Instalar dependencias ─────────────────────────────────────
echo "[→] Instalando dependencias Python..."
pip install --upgrade pip -q
pip install -r "$SCRIPT_DIR/requirements.txt" -q
echo "[✓] Dependencias instaladas"

# ── Crear directorios necesarios ──────────────────────────────
mkdir -p "$SCRIPT_DIR/backups"
mkdir -p "$SCRIPT_DIR/logs"
echo "[✓] Directorios 'backups' y 'logs' creados"

# ── Permisos del script ───────────────────────────────────────
chmod +x "$SCRIPT_DIR/antigravity_backup.py"

# ── Crear wrapper ejecutable ──────────────────────────────────
WRAPPER="/usr/local/bin/antigravity-backup"
sudo tee "$WRAPPER" > /dev/null <<EOF
#!/usr/bin/env bash
source "$SCRIPT_DIR/venv/bin/activate"
python3 "$SCRIPT_DIR/antigravity_backup.py" "\$@"
EOF
sudo chmod +x "$WRAPPER"
echo "[✓] Comando 'antigravity-backup' disponible en PATH"

# ── Instrucciones de cron ──────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════════"
echo "  Instalación completada."
echo ""
echo "  Para programar el backup diario a las 02:00 AM:"
echo ""
echo "  Ejecuta:  crontab -e"
echo "  Y añade:  0 2 * * * antigravity-backup --config $SCRIPT_DIR/config.yaml >> $SCRIPT_DIR/logs/cron.log 2>&1"
echo ""
echo "  Edita la configuración antes de ejecutar:"
echo "    nano $SCRIPT_DIR/config.yaml"
echo "══════════════════════════════════════════════════════"
echo ""
