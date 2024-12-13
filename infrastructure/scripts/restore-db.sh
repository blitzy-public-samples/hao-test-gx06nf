#!/usr/bin/env bash

# PostgreSQL Database Restore Script
# Version: 1.0.0
# Dependencies:
# - postgresql-client (14+): pg_restore utility
# - google-cloud-sdk (latest): gsutil for GCS operations

# Exit on error, undefined variables, and pipe failures
set -euo pipefail

# Trap errors and interrupts
trap 'error_handler $? $LINENO $BASH_LINENO "$BASH_COMMAND" $(printf "::%s" ${FUNCNAME[@]:-})' ERR
trap 'cleanup ${RESTORE_TEMP_DIR:-/tmp/restore}' EXIT

# Environment variables with defaults
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-app}"
DB_USER="${DB_USER:-postgres}"
DB_PASSWORD="${DB_PASSWORD:-postgres}"
BACKUP_BUCKET="${BACKUP_BUCKET:-gs://app-backups}"
RESTORE_TEMP_DIR="${RESTORE_TEMP_DIR:-/tmp/restore}"
BACKUP_FORMAT="${BACKUP_FORMAT:-custom}"
PARALLEL_JOBS="${PARALLEL_JOBS:-4}"
MAX_RETRIES="${MAX_RETRIES:-3}"
RETRY_DELAY="${RETRY_DELAY:-5}"
LOG_FILE="${LOG_FILE:-/var/log/db-restore.log}"

# Color codes for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly NC='\033[0m' # No Color

# Error handler function
error_handler() {
    local exit_code=$1
    local line_no=$2
    local bash_lineno=$3
    local last_command=$4
    local func_trace=$5

    echo -e "${RED}Error occurred in script at line: ${line_no}${NC}" >&2
    echo -e "${RED}Command: ${last_command}${NC}" >&2
    echo -e "${RED}Exit code: ${exit_code}${NC}" >&2
    echo "$(date '+%Y-%m-%d %H:%M:%S') ERROR: Script failed at line ${line_no}, command: ${last_command}" >> "${LOG_FILE}"
}

# Logging function
log() {
    local level=$1
    shift
    local message=$*
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "${timestamp} ${level}: ${message}" >> "${LOG_FILE}"
    
    case ${level} in
        INFO)  echo -e "${GREEN}${message}${NC}" ;;
        WARN)  echo -e "${YELLOW}${message}${NC}" ;;
        ERROR) echo -e "${RED}${message}${NC}" >&2 ;;
    esac
}

# Check prerequisites function
check_prerequisites() {
    log "INFO" "Checking prerequisites..."
    
    # Check pg_restore
    if ! command -v pg_restore >/dev/null 2>&1; then
        log "ERROR" "pg_restore not found. Please install postgresql-client."
        return 1
    fi
    
    # Check gsutil
    if ! command -v gsutil >/dev/null 2>&1; then
        log "ERROR" "gsutil not found. Please install google-cloud-sdk."
        return 1
    }
    
    # Verify GCP authentication
    if ! gsutil ls "${BACKUP_BUCKET}" >/dev/null 2>&1; then
        log "ERROR" "Unable to access backup bucket. Check GCP authentication."
        return 1
    }
    
    # Check database connectivity
    if ! PGPASSWORD="${DB_PASSWORD}" psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d postgres -c '\q' >/dev/null 2>&1; then
        log "ERROR" "Unable to connect to database. Check credentials."
        return 1
    }
    
    # Check temp directory
    mkdir -p "${RESTORE_TEMP_DIR}"
    if [ ! -w "${RESTORE_TEMP_DIR}" ]; then
        log "ERROR" "Cannot write to temporary directory: ${RESTORE_TEMP_DIR}"
        return 1
    }
    
    log "INFO" "Prerequisites check passed"
    return 0
}

# List available backups
list_available_backups() {
    log "INFO" "Listing available backups..."
    
    local backup_list
    backup_list=$(gsutil ls -l "${BACKUP_BUCKET}/**/*.backup" 2>/dev/null || echo "")
    
    if [ -z "${backup_list}" ]; then
        log "ERROR" "No backups found in ${BACKUP_BUCKET}"
        return 1
    }
    
    echo "Available backups:"
    echo "${backup_list}" | while read -r line; do
        local backup_name
        backup_name=$(echo "${line}" | awk '{print $3}')
        local backup_size
        backup_size=$(echo "${line}" | awk '{print $1}')
        local backup_date
        backup_date=$(echo "${line}" | awk '{print $2}')
        echo "Name: ${backup_name##*/}, Size: ${backup_size}, Date: ${backup_date}"
    done
    
    return 0
}

# Download backup function
download_backup() {
    local backup_name=$1
    local local_path=$2
    
    log "INFO" "Downloading backup: ${backup_name}"
    
    # Create temp directory with secure permissions
    mkdir -p "${local_path}"
    chmod 700 "${local_path}"
    
    # Download with retry logic
    local retry_count=0
    while [ ${retry_count} -lt ${MAX_RETRIES} ]; do
        if gsutil cp "${BACKUP_BUCKET}/${backup_name}" "${local_path}/" 2>/dev/null; then
            break
        fi
        retry_count=$((retry_count + 1))
        log "WARN" "Download failed, retrying in ${RETRY_DELAY} seconds (${retry_count}/${MAX_RETRIES})"
        sleep "${RETRY_DELAY}"
    done
    
    if [ ${retry_count} -eq ${MAX_RETRIES} ]; then
        log "ERROR" "Failed to download backup after ${MAX_RETRIES} attempts"
        return 1
    fi
    
    # Verify download
    if [ ! -f "${local_path}/${backup_name}" ]; then
        log "ERROR" "Backup file not found after download"
        return 1
    }
    
    log "INFO" "Backup downloaded successfully"
    return 0
}

# Restore database function
restore_database() {
    local backup_path=$1
    
    log "INFO" "Starting database restore..."
    
    # Terminate existing connections
    PGPASSWORD="${DB_PASSWORD}" psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d postgres \
        -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${DB_NAME}' AND pid <> pg_backend_pid();" >/dev/null 2>&1
    
    # Drop and recreate database
    PGPASSWORD="${DB_PASSWORD}" psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d postgres \
        -c "DROP DATABASE IF EXISTS ${DB_NAME};" \
        -c "CREATE DATABASE ${DB_NAME} WITH ENCODING 'UTF8';" >/dev/null 2>&1
    
    # Perform restore with parallel processing
    if ! PGPASSWORD="${DB_PASSWORD}" pg_restore \
        -h "${DB_HOST}" \
        -p "${DB_PORT}" \
        -U "${DB_USER}" \
        -d "${DB_NAME}" \
        -j "${PARALLEL_JOBS}" \
        -Fc \
        "${backup_path}" 2>>"${LOG_FILE}"; then
        log "ERROR" "Database restore failed"
        return 1
    }
    
    log "INFO" "Database restore completed successfully"
    return 0
}

# Cleanup function
cleanup() {
    local temp_path=$1
    
    log "INFO" "Performing cleanup..."
    
    # Secure removal of temporary files
    if [ -d "${temp_path}" ]; then
        find "${temp_path}" -type f -exec shred -u {} \;
        rm -rf "${temp_path}"
    fi
    
    log "INFO" "Cleanup completed"
    return 0
}

# Main function
main() {
    local backup_name=$1
    
    log "INFO" "Starting database restore process"
    
    # Check prerequisites
    if ! check_prerequisites; then
        log "ERROR" "Prerequisites check failed"
        return 1
    }
    
    # Create temporary directory
    local temp_dir="${RESTORE_TEMP_DIR}/restore_$(date +%Y%m%d_%H%M%S)"
    
    # Download backup
    if ! download_backup "${backup_name}" "${temp_dir}"; then
        log "ERROR" "Backup download failed"
        return 1
    }
    
    # Restore database
    if ! restore_database "${temp_dir}/${backup_name}"; then
        log "ERROR" "Database restore failed"
        return 1
    }
    
    log "INFO" "Database restore process completed successfully"
    return 0
}

# Script execution
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <backup_name>"
    exit 1
fi

main "$1"