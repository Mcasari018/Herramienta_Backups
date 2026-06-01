# 🛡️ SecureVault Backup

> **Script de copias de seguridad automatizadas** para directorios críticos y bases de datos.  
> Compatible con **Windows Server** y **Ubuntu/Debian Server**.

---

## 📋 Tabla de Contenidos

1. [¿Qué hace?](#-qué-hace)
2. [Arquitectura del proyecto](#-arquitectura-del-proyecto)
3. [Requisitos previos](#-requisitos-previos)
4. [Instalación rápida](#-instalación-rápida)
   - [Ubuntu / Debian Server](#ubuntu--debian-server)
   - [Windows Server](#windows-server)
5. [Configuración detallada](#-configuración-detallada)
   - [Directorios a respaldar](#directorios-a-respaldar)
   - [Bases de datos MySQL](#bases-de-datos-mysql)
   - [Bases de datos PostgreSQL](#bases-de-datos-postgresql)
   - [Almacenamiento local y retención](#almacenamiento-local-y-retención)
   - [Transferencia SSH/SFTP](#transferencia-sshsftp)
   - [Subida a AWS S3](#subida-a-aws-s3)
   - [Notificaciones por correo](#notificaciones-por-correo)
   - [Logging](#logging)
6. [Uso del script](#-uso-del-script)
7. [Automatización](#-automatización)
   - [Cron (Linux)](#cron-linux)
   - [Programador de Tareas (Windows)](#programador-de-tareas-windows)
8. [Flujo de ejecución](#-flujo-de-ejecución)
9. [Solución de problemas](#-solución-de-problemas)
10. [Seguridad — Buenas prácticas](#-seguridad--buenas-prácticas)

---

## 🔍 ¿Qué hace?

**SecureVault Backup** es un script Python profesional que automatiza el proceso completo de respaldo:

| Capacidad | Detalle |
|---|---|
| 📁 **Directorios** | Respalda cualquier directorio (rutas Linux y Windows) |
| 🗄️ **MySQL / MariaDB** | Genera dumps con `mysqldump` de una o varias bases de datos |
| 🐘 **PostgreSQL** | Genera dumps con `pg_dump` de una o varias bases de datos |
| 📦 **Compresión** | Empaqueta todo en un `.tar.gz` con timestamp y hostname |
| 🔐 **SSH / SFTP** | Envía el backup a un servidor remoto mediante `paramiko` |
| ☁️ **AWS S3** | Sube el backup a un bucket S3 con clase de almacenamiento configurable |
| 🗑️ **Retención** | Elimina automáticamente backups locales más antiguos de N días |
| 📧 **Notificaciones** | Envía email en caso de éxito o fallo vía SMTP |
| 📝 **Logs rotativos** | Registro completo con rotación automática por tamaño |
| 🔄 **Dry-run** | Simula la ejecución completa sin crear ni enviar nada |

---

## 🗂️ Arquitectura del proyecto

```
herramienta_backups/
│
├── securevault_backup.py   # Script principal (toda la lógica)
├── config.yaml             # Configuración (¡edita esto primero!)
├── requirements.txt        # Dependencias Python
│
├── install.sh              # Instalador para Ubuntu/Debian
├── install.ps1             # Instalador para Windows Server
│
├── backups/                # Backups .tar.gz generados (auto-creado)
└── logs/                   # Archivos de log (auto-creado)
    └── securevault_backup.log
```

El archivo `.tar.gz` generado sigue este esquema de nombres:

```
securevault_backup_<hostname>_<YYYYMMDD_HHMMSS>.tar.gz
```

Ejemplo: `securevault_backup_webserver01_20260601_020000.tar.gz`

### Estructura interna del .tar.gz

```
securevault_backup_*.tar.gz
├── var/www/html/           # Directorio respaldado (ruta relativa)
├── databases/
│   ├── mysql_mi_app.sql    # Dump de MySQL
│   └── postgresql_logs.sql # Dump de PostgreSQL
```

---

## ⚙️ Requisitos previos

### Todos los sistemas
- **Python 3.9 o superior**
- Las dependencias listadas en `requirements.txt`

### Linux (Ubuntu/Debian)
```bash
# Verificar versión de Python
python3 --version

# Si no está instalado:
sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv
```

### Windows Server
- Python 3.9+ descargado desde [python.org](https://www.python.org/downloads/)
- Marcar ✅ **"Add Python to PATH"** durante la instalación
- PowerShell 5.1+ (incluido en Windows Server 2016+)

### Herramientas de base de datos (opcionales)
- **MySQL/MariaDB**: cliente `mysqldump` en PATH  
  Ubuntu: `sudo apt-get install mysql-client`  
  Windows: incluido con MySQL Server o [MySQL Shell](https://dev.mysql.com/downloads/shell/)
  
- **PostgreSQL**: cliente `pg_dump` en PATH  
  Ubuntu: `sudo apt-get install postgresql-client`  
  Windows: incluido con PostgreSQL o [pgAdmin](https://www.pgadmin.org/)

---

## 🚀 Instalación rápida

### Ubuntu / Debian Server

```bash
# 1. Clonar o copiar el proyecto
cd /opt
sudo mkdir securevault_backup && sudo chown $USER: securevault_backup
# Copiar los archivos aquí...

# 2. Dar permisos al instalador
chmod +x install.sh

# 3. Ejecutar el instalador
./install.sh
```

El instalador automáticamente:
- Instala Python 3 si no está disponible
- Crea un entorno virtual en `./venv`
- Instala todas las dependencias
- Crea los directorios `backups/` y `logs/`
- Registra el comando `securevault-backup` en `/usr/local/bin`

---

### Windows Server

```powershell
# Abrir PowerShell como Administrador y ejecutar:
Set-ExecutionPolicy Bypass -Scope Process -Force
.\install.ps1
```

El instalador automáticamente:
- Verifica Python 3.9+
- Crea un entorno virtual en `.\venv`
- Instala todas las dependencias
- Crea los directorios `backups\` y `logs\`
- Registra una **Tarea Programada** diaria a las 02:00 AM

---

## 🔧 Configuración detallada

Abre `config.yaml` y edita cada sección según tus necesidades.

---

### Directorios a respaldar

```yaml
backup:
  directories:
    - "/var/www/html"          # Linux
    - "/home/usuario/datos"
    # - "C:\\inetpub\\wwwroot" # Windows (doble barra invertida)
    # - "D:\\datos\\criticos"
```

> **Nota**: puedes especificar múltiples rutas. Las rutas inexistentes se omiten con un aviso en el log.

---

### Bases de datos MySQL

```yaml
backup:
  mysql:
    enabled: true          # Cambiar a true para activar
    host: "localhost"
    port: 3306
    user: "backup_user"    # Usuario con permisos SELECT y LOCK TABLES
    password: "contraseña_segura"
    databases:
      - "app_produccion"
      - "usuarios"
    mysqldump_path: ""     # Dejar vacío para auto-detectar en PATH
```

**Usuario MySQL recomendado para backups** (mínimos privilegios):
```sql
CREATE USER 'backup_user'@'localhost' IDENTIFIED BY 'contraseña_segura';
GRANT SELECT, LOCK TABLES, SHOW VIEW, EVENT, TRIGGER ON *.* TO 'backup_user'@'localhost';
FLUSH PRIVILEGES;
```

---

### Bases de datos PostgreSQL

```yaml
backup:
  postgresql:
    enabled: true
    host: "localhost"
    port: 5432
    user: "backup_user"
    password: "contraseña_segura"
    databases:
      - "app_produccion"
    pg_dump_path: ""       # Dejar vacío para auto-detectar en PATH
```

**Usuario PostgreSQL recomendado**:
```sql
CREATE USER backup_user WITH PASSWORD 'contraseña_segura';
GRANT CONNECT ON DATABASE app_produccion TO backup_user;
GRANT USAGE ON SCHEMA public TO backup_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO backup_user;
```

---

### Almacenamiento local y retención

```yaml
storage:
  local_backup_dir: "./backups"  # Ruta local donde se guardan los .tar.gz
  retention_days: 7              # Eliminar backups locales > 7 días (0 = nunca)
```

Ejemplos de rutas:
- Linux: `/mnt/nas/backups` o `/var/backups/securevault`
- Windows: `D:\\Backups\\SecureVault`

---

### Transferencia SSH/SFTP

```yaml
ssh:
  enabled: true
  host: "192.168.1.100"
  port: 22
  user: "backup_user"
  private_key_path: "~/.ssh/id_rsa"   # Recomendado: autenticación por clave
  password: ""                          # O por contraseña (menos seguro)
  remote_dir: "/backups/securevault"
```

**Configurar autenticación por clave SSH** (recomendado):

```bash
# En tu máquina local / servidor de origen:
ssh-keygen -t ed25519 -C "securevault-backup" -f ~/.ssh/backup_key

# Copiar clave pública al servidor remoto:
ssh-copy-id -i ~/.ssh/backup_key.pub backup_user@192.168.1.100

# Verificar conexión:
ssh -i ~/.ssh/backup_key backup_user@192.168.1.100
```

Luego en `config.yaml`:
```yaml
private_key_path: "~/.ssh/backup_key"
```

---

### Subida a AWS S3

```yaml
s3:
  enabled: true
  bucket_name: "mi-empresa-backups"
  prefix: "servers/webserver01/"    # Carpeta virtual dentro del bucket
  region: "eu-west-1"
  access_key_id: ""                 # Vacío = usa perfil AWS CLI
  secret_access_key: ""
  storage_class: "STANDARD_IA"     # Ver tabla abajo
```

**Clases de almacenamiento S3 disponibles:**

| Clase | Uso recomendado | Coste |
|---|---|---|
| `STANDARD` | Acceso frecuente | Alto |
| `STANDARD_IA` | Backups recientes (< 30 días) | Medio |
| `GLACIER` | Archivado a largo plazo | Bajo |
| `DEEP_ARCHIVE` | Retención > 1 año | Muy bajo |

**Configurar credenciales AWS** (opción recomendada — perfil CLI):

```bash
# Instalar AWS CLI
pip install awscli

# Configurar credenciales (se guardan en ~/.aws/credentials)
aws configure
# AWS Access Key ID: AKIAIOSFODNN7EXAMPLE
# AWS Secret Access Key: wJalrXUtnFEMI/K7MDENG/...
# Default region name: eu-west-1
# Default output format: json
```

**Política IAM mínima para el usuario de backups:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::mi-empresa-backups",
        "arn:aws:s3:::mi-empresa-backups/*"
      ]
    }
  ]
}
```

---

### Notificaciones por correo

```yaml
notifications:
  enabled: true
  smtp_host: "smtp.gmail.com"
  smtp_port: 587
  smtp_user: "backups@tuempresa.com"
  smtp_password: "app_password_aqui"   # App Password, no tu contraseña real
  from_addr: "backups@tuempresa.com"
  to_addrs:
    - "sysadmin@tuempresa.com"
    - "devops@tuempresa.com"
  notify_on_success: true
  notify_on_failure: true
```

> **Gmail**: usa una [App Password](https://support.google.com/accounts/answer/185833) en lugar de tu contraseña principal. Activa la verificación en 2 pasos primero.

---

### Logging

```yaml
logging:
  log_file: "./logs/securevault_backup.log"
  log_level: "INFO"       # DEBUG | INFO | WARNING | ERROR
  max_log_size_mb: 10     # Rotar cuando el log supere 10 MB
  backup_count: 5         # Mantener hasta 5 logs rotados
```

---

## 💻 Uso del script

### Ejecución básica

```bash
# Linux (con entorno virtual)
source venv/bin/activate
python3 securevault_backup.py

# Linux (si instalaste con install.sh)
securevault-backup

# Windows (con entorno virtual)
.\venv\Scripts\activate
python securevault_backup.py
```

### Opciones de línea de comandos

```
securevault_backup.py [-h] [--config RUTA] [--dry-run] [--version]

Opciones:
  -h, --help            Muestra esta ayuda
  -c, --config RUTA     Ruta al config.yaml (default: ./config.yaml)
  -n, --dry-run         Simula sin crear ni enviar archivos
  -v, --version         Muestra la versión
```

### Ejemplos

```bash
# Usar un archivo de configuración personalizado
python3 securevault_backup.py --config /etc/securevault/production.yaml

# Simular ejecución completa (dry-run) — ideal para probar la config
python3 securevault_backup.py --dry-run

# Modo debug (más verboso)
# Cambia log_level a "DEBUG" en config.yaml
```

---

## ⏰ Automatización

### Cron (Linux)

```bash
# Editar el crontab del usuario o root
crontab -e

# Backup diario a las 02:00 AM
0 2 * * * /opt/securevault_backup/venv/bin/python3 /opt/securevault_backup/securevault_backup.py --config /opt/securevault_backup/config.yaml

# Backup cada 6 horas
0 */6 * * * securevault-backup --config /opt/securevault_backup/config.yaml

# Backup semanal (domingos a las 03:00)
0 3 * * 0 securevault-backup
```

**Verificar que cron está ejecutando el backup:**
```bash
# Ver el log del cron del sistema
grep "securevault" /var/log/syslog

# Ver el log del script
tail -f /opt/securevault_backup/logs/securevault_backup.log
```

---

### Programador de Tareas (Windows)

El instalador `install.ps1` crea la tarea automáticamente. Para gestionarla manualmente:

```powershell
# Ver la tarea creada
Get-ScheduledTask -TaskName "SecureVaultBackup"

# Ejecutar manualmente la tarea
Start-ScheduledTask -TaskName "SecureVaultBackup"

# Modificar el horario (ej: cada 4 horas)
$Trigger = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Hours 4) -Once -At (Get-Date)
Set-ScheduledTask -TaskName "SecureVaultBackup" -Trigger $Trigger

# Eliminar la tarea
Unregister-ScheduledTask -TaskName "SecureVaultBackup" -Confirm:$false
```

También puedes gestionar la tarea desde la GUI:  
**Inicio → Programador de Tareas → Biblioteca → SecureVaultBackup**

---

## 🔄 Flujo de ejecución

```
securevault_backup.py
│
├─ 1. Cargar config.yaml
├─ 2. Inicializar logging
│
├─ 3. [PASO 1] Dumps de bases de datos
│   ├─ mysqldump  → /tmp/xxxxx/mysql_<db>.sql
│   └─ pg_dump    → /tmp/xxxxx/postgresql_<db>.sql
│
├─ 4. [PASO 2] Compresión
│   └─ tar.gz ← directorios + dumps SQL
│       → backups/securevault_backup_<host>_<timestamp>.tar.gz
│
├─ 5. [PASO 3] Transferencia SSH/SFTP
│   └─ paramiko → servidor remoto
│
├─ 6. [PASO 4] Subida a AWS S3
│   └─ boto3 → s3://bucket/prefix/archivo.tar.gz
│
├─ 7. [PASO 5] Política de retención
│   └─ Elimina .tar.gz locales > retention_days
│
└─ 8. Notificación por correo (éxito/fallo)
```

---

## 🔧 Solución de problemas

### El script no encuentra `mysqldump` o `pg_dump`

**Linux:**
```bash
# MySQL
sudo apt-get install mysql-client
which mysqldump   # /usr/bin/mysqldump

# PostgreSQL
sudo apt-get install postgresql-client
which pg_dump     # /usr/bin/pg_dump
```

**Windows:**
```powershell
# Añadir al PATH (MySQL)
$env:PATH += ";C:\Program Files\MySQL\MySQL Server 8.0\bin"

# O especificar la ruta completa en config.yaml:
# mysqldump_path: "C:\\Program Files\\MySQL\\MySQL Server 8.0\\bin\\mysqldump.exe"
```

---

### Error de permisos al leer directorios (Linux)

```bash
# Ejecutar como root o con sudo
sudo python3 securevault_backup.py

# O dar permisos al usuario de backup
sudo usermod -aG www-data backup_user
```

---

### Error de autenticación SSH

```bash
# Probar la conexión manualmente
ssh -i ~/.ssh/id_rsa -v backup_user@servidor_remoto

# Verificar permisos de la clave privada (debe ser 600)
chmod 600 ~/.ssh/id_rsa

# Verificar que el directorio remoto existe
ssh backup_user@servidor_remoto "mkdir -p /backups/securevault"
```

---

### Error al subir a S3: `NoCredentialsError`

```bash
# Verificar que las credenciales AWS están configuradas
aws sts get-caller-identity

# O añadir las credenciales directamente en config.yaml:
# access_key_id: "AKIAIOSFODNN7EXAMPLE"
# secret_access_key: "wJalrXUtnFEMI..."
```

---

### El archivo .tar.gz existe pero está vacío o corrupto

```bash
# Verificar integridad del archivo
tar -tzf backups/securevault_backup_*.tar.gz

# Activar modo DEBUG para más información
# En config.yaml: log_level: "DEBUG"
python3 securevault_backup.py
```

---

## 🔒 Seguridad — Buenas prácticas

1. **No escribas contraseñas en config.yaml en texto plano** para entornos de producción.  
   Usa variables de entorno:
   ```yaml
   password: "${MYSQL_BACKUP_PASSWORD}"
   ```
   Y en el sistema:
   ```bash
   export MYSQL_BACKUP_PASSWORD="mi_contraseña_segura"
   ```

2. **Permisos del archivo de configuración** — solo el usuario del script debe leerlo:
   ```bash
   # Linux
   chmod 600 config.yaml
   chown backup_user: config.yaml
   ```

3. **Usa claves SSH con passphrase** para la transferencia remota.

4. **Encripta los backups** con GPG para datos sensibles:
   ```bash
   # Encriptar antes de enviar
   gpg --recipient admin@empresa.com --encrypt backup.tar.gz
   ```

5. **Rotación de credenciales**: cambia las contraseñas de los usuarios de backup periódicamente.

6. **Verifica los backups** regularmente haciendo un restore de prueba:
   ```bash
   # Extraer y verificar
   tar -xzf securevault_backup_*.tar.gz -C /tmp/restore_test/
   ```

---

## 📄 Licencia

MIT License — SecureVault © 2026
