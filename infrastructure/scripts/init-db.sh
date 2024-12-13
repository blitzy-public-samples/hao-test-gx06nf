#!/bin/bash

# Database initialization script for Specification Management API
# Version: 1.0.0
# Configures PostgreSQL database with proper schemas, users, and settings
# Supports both local PostgreSQL and Google Cloud SQL environments

set -e  # Exit on error
set -u  # Exit on undefined variables

# Import environment variables with defaults
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-}"
POSTGRES_DB="${POSTGRES_DB:-app}"
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
DB_POOL_SIZE="${DB_POOL_SIZE:-100}"
DB_POOL_TIMEOUT="${DB_POOL_TIMEOUT:-30}"
MAX_CONNECTIONS="${MAX_CONNECTIONS:-200}"
CLOUD_SQL_INSTANCE="${CLOUD_SQL_INSTANCE:-}"
ENVIRONMENT="${ENVIRONMENT:-development}"

# Configure logging
log() {
    echo "[$(date +'%Y-%m-%dT%H:%M:%S%z')] $@"
}

error() {
    echo "[$(date +'%Y-%m-%dT%H:%M:%S%z')] ERROR: $@" >&2
}

# Check PostgreSQL connection with retry logic
check_postgres_connection() {
    local retries=5
    local wait_time=5
    local connected=false

    while [ $retries -gt 0 ]; do
        if [ -n "$CLOUD_SQL_INSTANCE" ]; then
            # Cloud SQL connection using proxy
            if PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d postgres -c '\q' >/dev/null 2>&1; then
                connected=true
                break
            fi
        else
            # Local PostgreSQL connection
            if PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d postgres -c '\q' >/dev/null 2>&1; then
                connected=true
                break
            fi
        fi

        retries=$((retries - 1))
        if [ $retries -gt 0 ]; then
            log "Failed to connect to PostgreSQL. Retrying in $wait_time seconds..."
            sleep $wait_time
            wait_time=$((wait_time * 2))  # Exponential backoff
        fi
    done

    if [ "$connected" = false ]; then
        error "Failed to connect to PostgreSQL after multiple attempts"
        return 1
    fi

    log "Successfully connected to PostgreSQL"
    return 0
}

# Create and configure database
create_database() {
    log "Creating database and configuring settings..."

    # Create database if it doesn't exist
    PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d postgres <<EOF
        SELECT 'CREATE DATABASE $POSTGRES_DB' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$POSTGRES_DB');
EOF

    # Configure database parameters
    PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB <<EOF
        -- Enable required extensions
        CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
        CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

        -- Configure performance settings
        ALTER DATABASE $POSTGRES_DB SET timezone TO 'UTC';
        ALTER DATABASE $POSTGRES_DB SET statement_timeout TO '30s';
        ALTER DATABASE $POSTGRES_DB SET idle_in_transaction_session_timeout TO '60s';
        ALTER DATABASE $POSTGRES_DB SET lock_timeout TO '10s';

        -- Set security parameters
        ALTER DATABASE $POSTGRES_DB SET ssl TO on;
        ALTER DATABASE $POSTGRES_DB SET row_security TO on;
EOF

    log "Database creation and configuration completed"
}

# Configure connection pooling
configure_pooling() {
    log "Configuring connection pooling..."

    # Create pgbouncer configuration
    cat > /etc/pgbouncer/pgbouncer.ini <<EOF
[databases]
$POSTGRES_DB = host=$POSTGRES_HOST port=$POSTGRES_PORT dbname=$POSTGRES_DB

[pgbouncer]
pool_mode = transaction
max_client_conn = $MAX_CONNECTIONS
default_pool_size = $DB_POOL_SIZE
reserve_pool_size = 10
reserve_pool_timeout = 5
max_db_connections = $DB_POOL_SIZE
idle_transaction_timeout = $DB_POOL_TIMEOUT
server_reset_query = DISCARD ALL
server_check_delay = 30
server_check_query = select 1
server_lifetime = 3600
server_idle_timeout = 600
EOF

    # Configure SSL for Cloud SQL if needed
    if [ -n "$CLOUD_SQL_INSTANCE" ]; then
        cat >> /etc/pgbouncer/pgbouncer.ini <<EOF
server_tls_sslmode = verify-full
server_tls_ca_file = /etc/ssl/certs/ca-certificates.crt
EOF
    fi

    log "Connection pooling configuration completed"
}

# Configure monitoring
setup_monitoring() {
    log "Setting up database monitoring..."

    PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB <<EOF
        -- Enable statistics collector
        ALTER SYSTEM SET track_activities TO on;
        ALTER SYSTEM SET track_counts TO on;
        ALTER SYSTEM SET track_io_timing TO on;
        ALTER SYSTEM SET track_functions TO 'all';

        -- Configure statement logging
        ALTER SYSTEM SET log_min_duration_statement TO 1000;
        ALTER SYSTEM SET log_statement TO 'ddl';
        ALTER SYSTEM SET log_connections TO on;
        ALTER SYSTEM SET log_disconnections TO on;

        -- Setup performance monitoring
        ALTER SYSTEM SET shared_preload_libraries TO 'pg_stat_statements';
        ALTER SYSTEM SET pg_stat_statements.track TO 'all';
        ALTER SYSTEM SET pg_stat_statements.max TO 10000;
EOF

    log "Monitoring configuration completed"
}

# Run database migrations
run_migrations() {
    log "Running database migrations..."

    # Set PYTHONPATH to include application source
    export PYTHONPATH="/app/src/backend/src:$PYTHONPATH"

    # Create migration lock to prevent concurrent migrations
    if ! mkdir /tmp/db_migration.lock 2>/dev/null; then
        error "Another migration is in progress"
        return 1
    fi

    # Execute migrations
    python3 -c "from db.migrations.env import run_migrations_online; run_migrations_online()" || {
        error "Migration failed"
        rm -rf /tmp/db_migration.lock
        return 1
    }

    # Remove migration lock
    rm -rf /tmp/db_migration.lock
    log "Database migrations completed successfully"
}

# Main execution flow
main() {
    log "Starting database initialization for environment: $ENVIRONMENT"

    # Check PostgreSQL connection
    check_postgres_connection || exit 1

    # Create and configure database
    create_database || exit 1

    # Configure connection pooling
    configure_pooling || exit 1

    # Setup monitoring
    setup_monitoring || exit 1

    # Run migrations
    run_migrations || exit 1

    log "Database initialization completed successfully"
    return 0
}

# Execute main function
main "$@"