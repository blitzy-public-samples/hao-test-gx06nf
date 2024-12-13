#!/usr/bin/env bash

# PostgreSQL Database Backup Script with Google Cloud Storage Integration
# Version: 1.0.0
# Required tools: 
# - postgresql-client v14+ (pg_dump)
# - google-cloud-sdk (gsutil)

set -euo pipefail
IFS=$'\n\t'

# Environment variables with defaults
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-app}"
DB_USER="${DB_USER:-postgres}"
DB_PASSWORD="${DB_PASSWORD:-postgres}"
BACKUP_BUCKET="${BACKUP_BUCKET:-gs://app-backups}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
BACKUP_FORMAT="${BACKUP_FORMAT:-custom}"
COMPRESSION_LEVEL="${COMPRESSION_LEVEL:-9}"
MAX_RETRIES="${MAX_RETRIES:-3}"
PARALLEL_JOBS="${PARALLEL_JOBS:-2}"
BACKUP_ENCRYPTION="${BACKUP_ENCRYPTION:-AES256}"

# Constants
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
TEMP_DIR="/tmp/db_backup_${TIMESTAMP}"
LOG_FILE="${TEMP_DIR}/backup.log"
BACKUP_FILE="${TEMP_DIR}/${DB_NAME}_${TIMESTAMP}.backup"
CHECKSUM_FILE="${BACKUP_FILE}.sha256"

# Logging function
log() {
    local level=$1
    shift
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] [${level}] $*" | tee -a "${LOG_FILE}"
}

# Error handling function
error_handler() {
    local exit_code=$?
    log "ERROR" "An error occurred on line $1"
    cleanup
    exit "${exit_code}"
}

trap 'error_handler ${LINENO}' ERR

# Cleanup function
cleanup() {
    log "INFO" "Cleaning up temporary files..."
    if [[ -d "${TEMP_DIR}" ]]; then
        rm -rf "${TEMP_DIR}"
    fi
}

# Check prerequisites
check_prerequisites() {
    log "INFO" "Checking prerequisites..."
    
    # Check pg_dump
    if ! command -v pg_dump >/dev/null 2>&1; then
        log "ERROR" "pg_dump not found. Please install postgresql-client v14+"
        return 1
    fi
    
    # Check gsutil
    if ! command -v gsutil >/dev/null 2>&1; then
        log "ERROR" "gsutil not found. Please install google-cloud-sdk"
        return 1
    }
    
    # Verify gsutil authentication
    if ! gsutil ls "${BACKUP_BUCKET}" >/dev/null 2>&1; then
        log "ERROR" "Cannot access GCS bucket. Please check authentication and permissions"
        return 1
    }
    
    # Create temp directory
    mkdir -p "${TEMP_DIR}"
    
    # Check disk space
    local required_space=$((5 * 1024 * 1024)) # 5GB minimum
    local available_space=$(df -k "${TEMP_DIR}" | awk 'NR==2 {print $4}')
    if [[ ${available_space} -lt ${required_space} ]]; then
        log "ERROR" "Insufficient disk space. Required: 5GB, Available: $((available_space/1024/1024))GB"
        return 1
    }
    
    return 0
}

# Create database backup
create_backup() {
    log "INFO" "Starting database backup..."
    
    # Set PGPASSWORD for authentication
    export PGPASSWORD="${DB_PASSWORD}"
    
    # Backup command with retry logic
    local retry_count=0
    while [[ ${retry_count} -lt ${MAX_RETRIES} ]]; do
        if pg_dump \
            --host="${DB_HOST}" \
            --port="${DB_PORT}" \
            --username="${DB_USER}" \
            --dbname="${DB_NAME}" \
            --format="${BACKUP_FORMAT}" \
            --compress="${COMPRESSION_LEVEL}" \
            --jobs="${PARALLEL_JOBS}" \
            --verbose \
            --file="${BACKUP_FILE}" 2>> "${LOG_FILE}"; then
            
            log "INFO" "Backup completed successfully"
            break
        else
            retry_count=$((retry_count + 1))
            log "WARN" "Backup attempt ${retry_count} failed. Retrying..."
            sleep 5
        fi
    done
    
    if [[ ${retry_count} -eq ${MAX_RETRIES} ]]; then
        log "ERROR" "Backup failed after ${MAX_RETRIES} attempts"
        return 1
    fi
    
    # Generate checksum
    sha256sum "${BACKUP_FILE}" > "${CHECKSUM_FILE}"
    
    # Verify backup integrity
    if ! pg_restore --list "${BACKUP_FILE}" >/dev/null 2>&1; then
        log "ERROR" "Backup verification failed"
        return 1
    }
    
    return 0
}

# Upload to Google Cloud Storage
upload_to_gcs() {
    log "INFO" "Uploading backup to GCS..."
    
    local backup_size=$(stat -f%z "${BACKUP_FILE}")
    local metadata="timestamp=${TIMESTAMP},format=${BACKUP_FORMAT},size=${backup_size}"
    
    # Upload with retry logic
    local retry_count=0
    while [[ ${retry_count} -lt ${MAX_RETRIES} ]]; do
        if gsutil -o "GSUtil:parallel_composite_upload_threshold=150M" \
            -h "x-goog-meta-${metadata}" \
            -h "x-goog-storage-class=STANDARD" \
            cp "${BACKUP_FILE}" "${BACKUP_BUCKET}/" 2>> "${LOG_FILE}" && \
            gsutil cp "${CHECKSUM_FILE}" "${BACKUP_BUCKET}/"; then
            
            log "INFO" "Upload completed successfully"
            break
        else
            retry_count=$((retry_count + 1))
            log "WARN" "Upload attempt ${retry_count} failed. Retrying..."
            sleep 5
        fi
    done
    
    if [[ ${retry_count} -eq ${MAX_RETRIES} ]]; then
        log "ERROR" "Upload failed after ${MAX_RETRIES} attempts"
        return 1
    fi
    
    return 0
}

# Cleanup old backups
cleanup_old_backups() {
    log "INFO" "Cleaning up old backups..."
    
    local cutoff_date=$(date -d "${BACKUP_RETENTION_DAYS} days ago" +%Y%m%d)
    
    # List and filter old backups
    gsutil ls -l "${BACKUP_BUCKET}/**" | while read -r line; do
        local backup_date=$(echo "${line}" | grep -oP '\d{8}_\d{6}' || true)
        if [[ -n "${backup_date}" && "${backup_date:0:8}" < "${cutoff_date}" ]]; then
            local backup_path=$(echo "${line}" | awk '{print $3}')
            log "INFO" "Removing old backup: ${backup_path}"
            gsutil rm "${backup_path}" 2>> "${LOG_FILE}"
            gsutil rm "${backup_path}.sha256" 2>> "${LOG_FILE}" || true
        fi
    done
    
    return 0
}

# Main function
main() {
    log "INFO" "Starting backup process..."
    
    # Check prerequisites
    if ! check_prerequisites; then
        log "ERROR" "Prerequisites check failed"
        cleanup
        exit 1
    fi
    
    # Create backup
    if ! create_backup; then
        log "ERROR" "Backup creation failed"
        cleanup
        exit 1
    fi
    
    # Upload to GCS
    if ! upload_to_gcs; then
        log "ERROR" "Backup upload failed"
        cleanup
        exit 1
    fi
    
    # Cleanup old backups
    if ! cleanup_old_backups; then
        log "WARN" "Old backup cleanup failed"
    fi
    
    # Final cleanup
    cleanup
    
    log "INFO" "Backup process completed successfully"
    exit 0
}

# Execute main function
main