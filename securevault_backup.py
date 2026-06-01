#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║           ANTIGRAVITY BACKUP  v1.0.0                    ║
║   Automated Backup Script — Windows & Linux/Ubuntu      ║
╚══════════════════════════════════════════════════════════╝

Uso:
    python securevault_backup.py [--config ruta/config.yaml] [--dry-run]

Descripción:
    Realiza copias de seguridad de directorios y bases de datos
    (MySQL/PostgreSQL), las comprime en .tar.gz y las envía a
    un servidor remoto vía SSH/SFTP o a un bucket de AWS S3.

Autor : SecureVault
"""

import argparse
import logging
import logging.handlers
import os
import platform
import shutil
import smtplib
import subprocess
import sys
import tarfile
import tempfile
import traceback
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Optional

import yaml

# Force UTF-8 output for console to prevent UnicodeEncodeError on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')


# ── Importaciones opcionales ─────────────────────────────────
try:
    import paramiko
    HAS_PARAMIKO = True
except ImportError:
    HAS_PARAMIKO = False

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


# ═══════════════════════════════════════════════════════════════
#  Utilidades de plataforma
# ═══════════════════════════════════════════════════════════════

IS_WINDOWS = platform.system() == "Windows"


def normalize_path(p: str) -> Path:
    """Convierte rutas con ~ y variables de entorno a rutas absolutas."""
    return Path(os.path.expandvars(os.path.expanduser(p))).resolve()


def which(cmd: str) -> Optional[str]:
    """Busca un ejecutable en PATH (equivalente a which/where)."""
    return shutil.which(cmd)


# ═══════════════════════════════════════════════════════════════
#  Configuración de Logging
# ═══════════════════════════════════════════════════════════════

def setup_logging(log_file: str, log_level: str, max_mb: int, backup_count: int) -> logging.Logger:
    log_path = normalize_path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    level = getattr(logging, log_level.upper(), logging.INFO)
    logger = logging.getLogger("securevault_backup")
    logger.setLevel(level)

    # Archivo rotativo
    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=max_mb * 1024 * 1024,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(level)

    # Consola
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s  [%(levelname)-8s]  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(fmt)
    console_handler.setFormatter(fmt)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


# ═══════════════════════════════════════════════════════════════
#  Carga de configuración
# ═══════════════════════════════════════════════════════════════

def load_config(config_path: str) -> dict:
    path = normalize_path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo de configuración: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ═══════════════════════════════════════════════════════════════
#  Módulo: Backup de directorios
# ═══════════════════════════════════════════════════════════════

def backup_directories(directories: List[str], archive: tarfile.TarFile, logger: logging.Logger) -> int:
    """Añade directorios al archivo tar. Devuelve el número de directorios procesados."""
    count = 0
    for raw_dir in directories:
        src = normalize_path(raw_dir)
        if not src.exists():
            logger.warning(f"Directorio no encontrado, se omite: {src}")
            continue
        logger.info(f"  → Añadiendo directorio: {src}")
        # En Windows el separador es \, lo normalizamos en el tar a /
        arcname = str(src).replace("\\", "/").lstrip("/").lstrip(":")
        archive.add(str(src), arcname=arcname, recursive=True)
        count += 1
    return count


# ═══════════════════════════════════════════════════════════════
#  Módulo: Backup MySQL/MariaDB
# ═══════════════════════════════════════════════════════════════

def dump_mysql(cfg: dict, tmp_dir: str, logger: logging.Logger) -> List[str]:
    """Genera dumps de las bases de datos MySQL. Devuelve lista de archivos generados."""
    if not cfg.get("enabled", False):
        return []

    dump_bin = cfg.get("mysqldump_path") or which("mysqldump") or which("mysqldump.exe")
    if not dump_bin:
        logger.error("mysqldump no encontrado. Instala MySQL client tools o especifica 'mysqldump_path' en config.yaml")
        return []

    files = []
    env = os.environ.copy()
    # Usar MYSQL_PWD evita el warning de contraseña en CLI
    env["MYSQL_PWD"] = cfg.get("password", "")

    for db in cfg.get("databases", []):
        out_file = os.path.join(tmp_dir, f"mysql_{db}.sql")
        cmd = [
            dump_bin,
            f"--host={cfg['host']}",
            f"--port={cfg['port']}",
            f"--user={cfg['user']}",
            "--single-transaction",
            "--quick",
            "--lock-tables=false",
            db,
        ]
        logger.info(f"  → Dumping MySQL DB: {db}")
        try:
            with open(out_file, "w", encoding="utf-8") as out:
                result = subprocess.run(cmd, env=env, stdout=out, stderr=subprocess.PIPE, timeout=3600)
            if result.returncode != 0:
                logger.error(f"    mysqldump falló para '{db}': {result.stderr.decode()}")
            else:
                logger.info(f"    Dump guardado: {out_file}")
                files.append(out_file)
        except subprocess.TimeoutExpired:
            logger.error(f"    Timeout al hacer dump de '{db}'")
        except Exception as exc:
            logger.error(f"    Error inesperado en dump MySQL '{db}': {exc}")
    return files


# ═══════════════════════════════════════════════════════════════
#  Módulo: Backup PostgreSQL
# ═══════════════════════════════════════════════════════════════

def dump_postgresql(cfg: dict, tmp_dir: str, logger: logging.Logger) -> List[str]:
    """Genera dumps de las bases de datos PostgreSQL. Devuelve lista de archivos generados."""
    if not cfg.get("enabled", False):
        return []

    dump_bin = cfg.get("pg_dump_path") or which("pg_dump") or which("pg_dump.exe")
    if not dump_bin:
        logger.error("pg_dump no encontrado. Instala PostgreSQL client tools o especifica 'pg_dump_path' en config.yaml")
        return []

    files = []
    env = os.environ.copy()
    env["PGPASSWORD"] = cfg.get("password", "")

    for db in cfg.get("databases", []):
        out_file = os.path.join(tmp_dir, f"postgresql_{db}.sql")
        cmd = [
            dump_bin,
            f"--host={cfg['host']}",
            f"--port={cfg['port']}",
            f"--username={cfg['user']}",
            "--format=plain",
            "--no-password",
            db,
        ]
        logger.info(f"  → Dumping PostgreSQL DB: {db}")
        try:
            with open(out_file, "w", encoding="utf-8") as out:
                result = subprocess.run(cmd, env=env, stdout=out, stderr=subprocess.PIPE, timeout=3600)
            if result.returncode != 0:
                logger.error(f"    pg_dump falló para '{db}': {result.stderr.decode()}")
            else:
                logger.info(f"    Dump guardado: {out_file}")
                files.append(out_file)
        except subprocess.TimeoutExpired:
            logger.error(f"    Timeout al hacer dump de '{db}'")
        except Exception as exc:
            logger.error(f"    Error inesperado en dump PostgreSQL '{db}': {exc}")
    return files


# ═══════════════════════════════════════════════════════════════
#  Módulo: Compresión
# ═══════════════════════════════════════════════════════════════

def create_archive(
    archive_path: str,
    directories: List[str],
    extra_files: List[str],
    logger: logging.Logger,
    dry_run: bool = False,
) -> bool:
    """
    Crea un archivo .tar.gz con los directorios y archivos extra.
    Devuelve True si tuvo éxito.
    """
    if dry_run:
        logger.info(f"[DRY-RUN] Se crearía el archivo: {archive_path}")
        return True

    logger.info(f"Creando archivo comprimido: {archive_path}")
    try:
        with tarfile.open(archive_path, "w:gz") as tar:
            backup_directories(directories, tar, logger)
            for f in extra_files:
                arcname = os.path.join("databases", os.path.basename(f))
                logger.info(f"  → Añadiendo dump de BD: {arcname}")
                tar.add(f, arcname=arcname)
        size_mb = os.path.getsize(archive_path) / (1024 * 1024)
        logger.info(f"Archivo creado correctamente ({size_mb:.2f} MB): {archive_path}")
        return True
    except Exception as exc:
        logger.error(f"Error al crear el archivo: {exc}")
        logger.debug(traceback.format_exc())
        return False


# ═══════════════════════════════════════════════════════════════
#  Módulo: Transferencia SSH/SFTP
# ═══════════════════════════════════════════════════════════════

def upload_ssh(cfg: dict, local_file: str, logger: logging.Logger, dry_run: bool = False) -> bool:
    if not cfg.get("enabled", False):
        return True  # No configurado, se considera OK

    if not HAS_PARAMIKO:
        logger.error("paramiko no instalado. Ejecuta: pip install paramiko")
        return False

    if dry_run:
        logger.info(f"[DRY-RUN] Se subiría por SSH a {cfg['host']}:{cfg['remote_dir']}")
        return True

    host = cfg["host"]
    port = int(cfg.get("port", 22))
    user = cfg["user"]
    remote_dir = cfg["remote_dir"]
    remote_filename = os.path.basename(local_file)
    remote_path = f"{remote_dir}/{remote_filename}"

    logger.info(f"Subiendo via SFTP → {user}@{host}:{remote_path}")

    try:
        transport = paramiko.Transport((host, port))

        key_path_raw = cfg.get("private_key_path", "")
        password = cfg.get("password", "")

        if key_path_raw:
            key_path = normalize_path(key_path_raw)
            pkey = paramiko.RSAKey.from_private_key_file(str(key_path))
            transport.connect(username=user, pkey=pkey)
        else:
            transport.connect(username=user, password=password)

        sftp = paramiko.SFTPClient.from_transport(transport)

        # Crear directorio remoto si no existe
        try:
            sftp.stat(remote_dir)
        except FileNotFoundError:
            # Crear recursivamente
            parts = remote_dir.strip("/").split("/")
            current = ""
            for part in parts:
                current += f"/{part}"
                try:
                    sftp.stat(current)
                except FileNotFoundError:
                    sftp.mkdir(current)

        sftp.put(local_file, remote_path)
        sftp.close()
        transport.close()

        logger.info(f"  ✓ Subida SSH completada: {remote_path}")
        return True

    except Exception as exc:
        logger.error(f"Error al subir por SSH: {exc}")
        logger.debug(traceback.format_exc())
        return False


# ═══════════════════════════════════════════════════════════════
#  Módulo: Subida a AWS S3
# ═══════════════════════════════════════════════════════════════

def upload_s3(cfg: dict, local_file: str, logger: logging.Logger, dry_run: bool = False) -> bool:
    if not cfg.get("enabled", False):
        return True

    if not HAS_BOTO3:
        logger.error("boto3 no instalado. Ejecuta: pip install boto3")
        return False

    bucket = cfg["bucket_name"]
    prefix = cfg.get("prefix", "")
    region = cfg.get("region", "us-east-1")
    storage_class = cfg.get("storage_class", "STANDARD_IA")
    key = f"{prefix}{os.path.basename(local_file)}"

    if dry_run:
        logger.info(f"[DRY-RUN] Se subiría a s3://{bucket}/{key}")
        return True

    logger.info(f"Subiendo a AWS S3 → s3://{bucket}/{key}")

    try:
        kwargs = {"region_name": region}
        access_key = cfg.get("access_key_id", "")
        secret_key = cfg.get("secret_access_key", "")

        if access_key and secret_key:
            kwargs["aws_access_key_id"] = access_key
            kwargs["aws_secret_access_key"] = secret_key

        s3_client = boto3.client("s3", **kwargs)

        file_size = os.path.getsize(local_file)
        logger.info(f"  Tamaño del archivo: {file_size / (1024*1024):.2f} MB")

        s3_client.upload_file(
            local_file,
            bucket,
            key,
            ExtraArgs={"StorageClass": storage_class},
        )

        logger.info(f"  ✓ Subida a S3 completada: s3://{bucket}/{key}")
        return True

    except (BotoCoreError, ClientError) as exc:
        logger.error(f"Error al subir a S3: {exc}")
        logger.debug(traceback.format_exc())
        return False


# ═══════════════════════════════════════════════════════════════
#  Módulo: Retención (limpieza de backups antiguos)
# ═══════════════════════════════════════════════════════════════

def apply_retention(backup_dir: str, retention_days: int, logger: logging.Logger, dry_run: bool = False):
    if retention_days <= 0:
        return

    cutoff = datetime.now() - timedelta(days=retention_days)
    backup_path = normalize_path(backup_dir)
    deleted = 0

    for f in backup_path.glob("securevault_backup_*.tar.gz"):
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        if mtime < cutoff:
            if dry_run:
                logger.info(f"[DRY-RUN] Se eliminaría: {f.name} (modificado: {mtime:%Y-%m-%d})")
            else:
                logger.info(f"Eliminando backup antiguo: {f.name} (modificado: {mtime:%Y-%m-%d})")
                f.unlink()
            deleted += 1

    if deleted == 0:
        logger.info("No hay backups antiguos que eliminar.")
    else:
        logger.info(f"Retención aplicada: {deleted} archivo(s) eliminado(s).")


# ═══════════════════════════════════════════════════════════════
#  Módulo: Notificaciones por correo
# ═══════════════════════════════════════════════════════════════

def send_notification(cfg: dict, subject: str, body: str, logger: logging.Logger):
    if not cfg.get("enabled", False):
        return

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = cfg["from_addr"]
        msg["To"] = ", ".join(cfg["to_addrs"])
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP(cfg["smtp_host"], int(cfg["smtp_port"])) as server:
            server.starttls()
            server.login(cfg["smtp_user"], cfg["smtp_password"])
            server.sendmail(cfg["from_addr"], cfg["to_addrs"], msg.as_string())

        logger.info(f"Notificación enviada a: {', '.join(cfg['to_addrs'])}")
    except Exception as exc:
        logger.warning(f"No se pudo enviar la notificación: {exc}")


# ═══════════════════════════════════════════════════════════════
#  Punto de entrada principal
# ═══════════════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SecureVault Backup — Script de copias de seguridad automatizadas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config", "-c",
        default="config.yaml",
        help="Ruta al archivo de configuración (default: config.yaml)",
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Simula la ejecución sin crear ni enviar archivos",
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version="SecureVault Backup v1.0.0",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # ── Carga de configuración ────────────────────────────────
    try:
        cfg = load_config(args.config)
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as exc:
        print(f"[ERROR] Error al parsear config.yaml: {exc}", file=sys.stderr)
        sys.exit(1)

    # ── Logging ───────────────────────────────────────────────
    log_cfg = cfg.get("logging", {})
    logger = setup_logging(
        log_file=log_cfg.get("log_file", "./logs/securevault_backup.log"),
        log_level=log_cfg.get("log_level", "INFO"),
        max_mb=log_cfg.get("max_log_size_mb", 10),
        backup_count=log_cfg.get("backup_count", 5),
    )

    logger.info("=" * 60)
    logger.info("  ANTIGRAVITY BACKUP  v1.0.0")
    logger.info(f"  Sistema: {platform.system()} {platform.release()}")
    logger.info(f"  Python:  {sys.version.split()[0]}")
    if args.dry_run:
        logger.info("  MODO DRY-RUN activado (no se crearán archivos)")
    logger.info("=" * 60)

    success = True
    start_time = datetime.now()
    archive_path = None

    try:
        backup_cfg = cfg.get("backup", {})
        storage_cfg = cfg.get("storage", {})

        # ── Directorio local de backups ───────────────────────
        local_dir = normalize_path(storage_cfg.get("local_backup_dir", "./backups"))
        if not args.dry_run:
            local_dir.mkdir(parents=True, exist_ok=True)

        # ── Nombre del archivo con timestamp ──────────────────
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        hostname = platform.node().replace(" ", "_")
        archive_name = f"securevault_backup_{hostname}_{timestamp}.tar.gz"
        archive_path = str(local_dir / archive_name)

        # ── Dumps de bases de datos en directorio temporal ────
        db_files = []
        with tempfile.TemporaryDirectory() as tmp_dir:
            logger.info("── Paso 1: Dumps de bases de datos ──────────────────")
            db_files_mysql = dump_mysql(backup_cfg.get("mysql", {}), tmp_dir, logger)
            db_files_pg = dump_postgresql(backup_cfg.get("postgresql", {}), tmp_dir, logger)
            db_files = db_files_mysql + db_files_pg

            # ── Compresión ────────────────────────────────────
            logger.info("── Paso 2: Compresión del backup ────────────────────")
            ok = create_archive(
                archive_path=archive_path,
                directories=backup_cfg.get("directories", []),
                extra_files=db_files,
                logger=logger,
                dry_run=args.dry_run,
            )
            if not ok:
                success = False

        # ── Transferencia SSH ──────────────────────────────────
        logger.info("── Paso 3: Transferencia SSH/SFTP ───────────────────")
        ok = upload_ssh(cfg.get("ssh", {}), archive_path, logger, dry_run=args.dry_run)
        if not ok:
            success = False

        # ── Subida a S3 ────────────────────────────────────────
        logger.info("── Paso 4: Subida a AWS S3 ──────────────────────────")
        ok = upload_s3(cfg.get("s3", {}), archive_path, logger, dry_run=args.dry_run)
        if not ok:
            success = False

        # ── Retención ──────────────────────────────────────────
        logger.info("── Paso 5: Política de retención ────────────────────")
        apply_retention(
            backup_dir=str(local_dir),
            retention_days=storage_cfg.get("retention_days", 7),
            logger=logger,
            dry_run=args.dry_run,
        )

    except KeyboardInterrupt:
        logger.warning("Interrupción por el usuario (Ctrl+C)")
        success = False
    except Exception as exc:
        logger.error(f"Error inesperado: {exc}")
        logger.debug(traceback.format_exc())
        success = False

    # ── Resumen final ──────────────────────────────────────────
    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info("=" * 60)
    if success:
        logger.info(f"  ✓ Backup completado en {elapsed:.1f}s")
        if archive_path:
            logger.info(f"  Archivo: {archive_path}")
        subject = f"[SecureVault Backup] ✓ Backup exitoso — {platform.node()}"
        body = (
            f"El backup se completó correctamente.\n\n"
            f"Host: {platform.node()}\n"
            f"Fecha: {datetime.now():%Y-%m-%d %H:%M:%S}\n"
            f"Duración: {elapsed:.1f}s\n"
            f"Archivo: {archive_path or 'N/A'}\n"
        )
        if cfg.get("notifications", {}).get("notify_on_success", True):
            send_notification(cfg.get("notifications", {}), subject, body, logger)
    else:
        logger.error(f"  ✗ Backup finalizado con errores en {elapsed:.1f}s")
        subject = f"[SecureVault Backup] ✗ Backup FALLIDO — {platform.node()}"
        body = (
            f"El backup finalizó con errores.\n\n"
            f"Host: {platform.node()}\n"
            f"Fecha: {datetime.now():%Y-%m-%d %H:%M:%S}\n"
            f"Duración: {elapsed:.1f}s\n\n"
            f"Revisa el log en: {log_cfg.get('log_file', './logs/securevault_backup.log')}\n"
        )
        if cfg.get("notifications", {}).get("notify_on_failure", True):
            send_notification(cfg.get("notifications", {}), subject, body, logger)

    logger.info("=" * 60)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
