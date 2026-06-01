#Requires -Version 5.1
<#
.SYNOPSIS
    SecureVault Backup - Instalador para Windows Server

.DESCRIPTION
    Instala las dependencias Python, crea el entorno virtual y
    configura una tarea programada en el Programador de Tareas de Windows
    para ejecutar el backup automaticamente.
#>

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

function Write-Header {
    Write-Host ""
    Write-Host "==================================================" -ForegroundColor Cyan
    Write-Host "    ANTIGRAVITY BACKUP - Instalador Windows       " -ForegroundColor Cyan
    Write-Host "==================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Step($msg) {
    Write-Host "[->] $msg" -ForegroundColor Yellow
}

function Write-OK($msg) {
    Write-Host "[OK] $msg" -ForegroundColor Green
}

function Write-Err($msg) {
    Write-Host "[XX] $msg" -ForegroundColor Red
}

# -- Header --
Write-Header

# -- Verificar Python --
Write-Step "Verificando Python 3..."
try {
    $pyVersion = & python --version 2>&1
    if ($pyVersion -notmatch "Python 3\.[9-9]|Python 3\.[1-9][0-9]") {
        Write-Err "Se requiere Python 3.9+. Encontrado: $pyVersion"
        Write-Host "Descarga Python desde: https://www.python.org/downloads/" -ForegroundColor White
        exit 1
    }
    Write-OK "$pyVersion detectado"
} catch {
    Write-Err "Python no encontrado en PATH."
    Write-Host "Descarga Python desde: https://www.python.org/downloads/" -ForegroundColor White
    exit 1
}

# -- Crear entorno virtual --
$VenvPath = Join-Path $ScriptDir "venv"
Write-Step "Creando entorno virtual en $VenvPath ..."
python -m venv $VenvPath
Write-OK "Entorno virtual creado"

# -- Instalar dependencias --
$PipExe  = Join-Path $VenvPath "Scripts\pip.exe"
$PyExe   = Join-Path $VenvPath "Scripts\python.exe"
$ReqFile = Join-Path $ScriptDir "requirements.txt"

Write-Step "Instalando dependencias Python..."
& $PipExe install --upgrade pip --quiet
& $PipExe install -r $ReqFile --quiet
Write-OK "Dependencias instaladas"

# -- Crear directorios necesarios --
$BackupDir = Join-Path $ScriptDir "backups"
$LogDir    = Join-Path $ScriptDir "logs"
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
New-Item -ItemType Directory -Force -Path $LogDir    | Out-Null
Write-OK "Directorios 'backups' y 'logs' creados"

# -- Crear tarea programada --
$TaskName   = "SecureVaultBackup"
$ScriptPath = Join-Path $ScriptDir "securevault_backup.py"
$ConfigPath = Join-Path $ScriptDir "config.yaml"
$LogPath    = Join-Path $LogDir "scheduled_backup.log"

Write-Step "Creando tarea programada '$TaskName' (diaria a las 02:00)..."

$Action  = New-ScheduledTaskAction -Execute $PyExe -Argument "`"$ScriptPath`" --config `"$ConfigPath`" >> `"$LogPath`" 2>&1" -WorkingDirectory $ScriptDir

$Trigger  = New-ScheduledTaskTrigger -Daily -At "02:00"
$Settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 4) -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 5)

$Principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

try {
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Description "SecureVault Backup - Copia de seguridad automatizada" -Force | Out-Null
    Write-OK "Tarea programada '$TaskName' registrada"
} catch {
    Write-Host "[!] No se pudo crear la tarea programada (ejecutando sin Administrador): $_" -ForegroundColor Yellow
}

# -- Resumen --
Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  Instalacion completada." -ForegroundColor Green
Write-Host ""
Write-Host "  Edita la configuracion antes del primer backup:" -ForegroundColor White
Write-Host "    notepad `"$ConfigPath`"" -ForegroundColor Gray
Write-Host ""
Write-Host "  Prueba sin crear archivos (dry-run):" -ForegroundColor White
Write-Host "    & `"$PyExe`" `"$ScriptPath`" --config `"$ConfigPath`" --dry-run" -ForegroundColor Gray
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""
