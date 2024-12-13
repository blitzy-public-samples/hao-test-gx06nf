#!/bin/bash

# Version: 1.0.0
# Specification Management API Rollback Script
# Provides automated rollback capability with health verification and audit logging
# Required tools: kubectl v1.24+, kustomize v4.5+, gcloud (latest)

set -euo pipefail

# Global variables
SCRIPT_DIR=$(dirname "${BASH_SOURCE[0]}")
PROJECT_ROOT=$(cd "${SCRIPT_DIR}/../.." && pwd)
MAX_WAIT_TIME=300  # 5 minutes RTO requirement
ROLLBACK_HISTORY_LIMIT=10
LOG_DIR="${PROJECT_ROOT}/logs/rollback"
HEALTH_CHECK_INTERVAL=5
HEALTH_CHECK_RETRIES=60
ALERT_THRESHOLD=0.8

# Ensure log directory exists
mkdir -p "${LOG_DIR}"

# Logging setup
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${LOG_DIR}/rollback_${TIMESTAMP}.log"
exec 1> >(tee -a "${LOG_FILE}")
exec 2> >(tee -a "${LOG_FILE}" >&2)

# Print usage information
print_usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS] ENVIRONMENT

Rolls back the Specification Management API deployment to a previous stable version.

Options:
    -h, --help              Show this help message
    -r, --revision NUMBER   Specific revision to rollback to (optional)
    -f, --force            Force rollback without health checks (use with caution)

Environment:
    staging                 Staging environment
    prod                    Production environment

Example:
    $(basename "$0") prod              # Rollback production to last stable version
    $(basename "$0") -r 2 staging      # Rollback staging to revision 2
EOF
}

# Validate deployment environment
validate_environment() {
    local env=$1
    if [[ "${env}" != "staging" && "${env}" != "prod" ]]; then
        echo "ERROR: Invalid environment '${env}'. Must be 'staging' or 'prod'" >&2
        return 1
    fi
    return 0
}

# Check required dependencies
check_dependencies() {
    local missing_deps=0

    echo "Checking dependencies..."

    # Check kubectl
    if ! command -v kubectl >/dev/null 2>&1; then
        echo "ERROR: kubectl is not installed (required v1.24+)" >&2
        missing_deps=1
    fi

    # Check kustomize
    if ! command -v kustomize >/dev/null 2>&1; then
        echo "ERROR: kustomize is not installed (required v4.5+)" >&2
        missing_deps=1
    fi

    # Check gcloud
    if ! command -v gcloud >/dev/null 2>&1; then
        echo "ERROR: gcloud SDK is not installed" >&2
        missing_deps=1
    fi

    # Verify cluster connectivity
    if ! kubectl cluster-info >/dev/null 2>&1; then
        echo "ERROR: Cannot connect to Kubernetes cluster" >&2
        missing_deps=1
    fi

    return $missing_deps
}

# Get previous stable revision
get_previous_revision() {
    local env=$1
    local namespace="spec-mgmt-${env}"
    local deployment="spec-mgmt-api"

    echo "Retrieving deployment history for ${deployment} in ${namespace}..."
    
    # Get deployment history
    local history
    history=$(kubectl rollout history deployment/${deployment} -n "${namespace}" 2>/dev/null)
    if [[ $? -ne 0 ]]; then
        echo "ERROR: Failed to retrieve deployment history" >&2
        return 1
    }

    # Parse revisions and find last stable one
    local revisions
    revisions=$(echo "${history}" | grep -E '^[0-9]+' | awk '{print $1}' | sort -nr)
    
    for rev in ${revisions}; do
        # Check revision stability metrics
        local stability
        stability=$(kubectl rollout history deployment/${deployment} -n "${namespace}" --revision="${rev}" 2>/dev/null | \
                   grep -E 'Successfully rolled out|Healthy' || true)
        
        if [[ -n "${stability}" ]]; then
            echo "${rev}"
            return 0
        fi
    done

    echo "ERROR: No stable revision found in history" >&2
    return 1
}

# Perform rollback operation
perform_rollback() {
    local env=$1
    local revision=$2
    local namespace="spec-mgmt-${env}"
    local deployment="spec-mgmt-api"
    local start_time
    start_time=$(date +%s)

    echo "Starting rollback for ${deployment} in ${namespace} to revision ${revision}..."
    
    # Create audit log entry
    echo "[$(date -u)] Starting rollback operation for ${env} environment to revision ${revision}" >> "${LOG_DIR}/audit.log"

    # Execute rollback
    if ! kubectl rollout undo deployment/${deployment} -n "${namespace}" --to-revision="${revision}"; then
        echo "ERROR: Rollback command failed" >&2
        return 1
    }

    # Monitor rollback progress with timeout
    local elapsed=0
    while [[ ${elapsed} -lt ${MAX_WAIT_TIME} ]]; do
        if kubectl rollout status deployment/${deployment} -n "${namespace}" --timeout=5s >/dev/null 2>&1; then
            echo "Rollback completed successfully"
            break
        fi
        
        elapsed=$(($(date +%s) - start_time))
        if [[ ${elapsed} -ge ${MAX_WAIT_TIME} ]]; then
            echo "ERROR: Rollback timed out after ${MAX_WAIT_TIME} seconds" >&2
            cleanup_failed_rollback "${env}"
            return 1
        fi
        
        sleep "${HEALTH_CHECK_INTERVAL}"
    done

    # Verify deployment health
    if ! verify_deployment_health "${env}"; then
        echo "ERROR: Health check failed after rollback" >&2
        cleanup_failed_rollback "${env}"
        return 1
    fi

    echo "[$(date -u)] Rollback completed successfully for ${env} environment" >> "${LOG_DIR}/audit.log"
    return 0
}

# Verify deployment health
verify_deployment_health() {
    local env=$1
    local namespace="spec-mgmt-${env}"
    local deployment="spec-mgmt-api"
    local retries=${HEALTH_CHECK_RETRIES}

    echo "Verifying deployment health..."

    while [[ ${retries} -gt 0 ]]; do
        # Check deployment status
        local ready_replicas
        ready_replicas=$(kubectl get deployment ${deployment} -n "${namespace}" -o jsonpath='{.status.readyReplicas}' 2>/dev/null)
        
        if [[ -z "${ready_replicas}" || "${ready_replicas}" -eq 0 ]]; then
            retries=$((retries - 1))
            sleep "${HEALTH_CHECK_INTERVAL}"
            continue
        fi

        # Verify pod health
        local unhealthy_pods
        unhealthy_pods=$(kubectl get pods -n "${namespace}" -l app=${deployment} \
                        -o jsonpath='{.items[?(@.status.phase!="Running")].metadata.name}')
        
        if [[ -n "${unhealthy_pods}" ]]; then
            retries=$((retries - 1))
            sleep "${HEALTH_CHECK_INTERVAL}"
            continue
        }

        # Check application health endpoint
        local health_check
        health_check=$(kubectl exec -n "${namespace}" -l app=${deployment} -- curl -s http://localhost:8000/health)
        
        if [[ "${health_check}" != *"healthy"* ]]; then
            retries=$((retries - 1))
            sleep "${HEALTH_CHECK_INTERVAL}"
            continue
        fi

        echo "Deployment health verified successfully"
        return 0
    done

    echo "ERROR: Health check failed after ${HEALTH_CHECK_RETRIES} retries" >&2
    return 1
}

# Cleanup after failed rollback
cleanup_failed_rollback() {
    local env=$1
    local namespace="spec-mgmt-${env}"
    local deployment="spec-mgmt-api"

    echo "Performing cleanup after failed rollback..."

    # Scale down deployment
    kubectl scale deployment ${deployment} -n "${namespace}" --replicas=0 2>/dev/null || true
    
    # Remove failed pods
    kubectl delete pods -n "${namespace}" -l app=${deployment} --force --grace-period=0 2>/dev/null || true
    
    # Log cleanup
    echo "[$(date -u)] Cleanup performed after failed rollback in ${env} environment" >> "${LOG_DIR}/audit.log"
    
    # Trigger alert
    echo "ALERT: Rollback failed for ${env} environment. Manual intervention required." >&2
}

# Main execution
main() {
    local environment=""
    local revision=""
    local force=false

    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                print_usage
                exit 0
                ;;
            -r|--revision)
                revision="$2"
                shift 2
                ;;
            -f|--force)
                force=true
                shift
                ;;
            staging|prod)
                environment="$1"
                shift
                ;;
            *)
                echo "ERROR: Unknown option $1" >&2
                print_usage
                exit 1
                ;;
        esac
    done

    # Validate inputs
    if [[ -z "${environment}" ]]; then
        echo "ERROR: Environment must be specified" >&2
        print_usage
        exit 1
    fi

    if ! validate_environment "${environment}"; then
        exit 1
    fi

    if ! check_dependencies; then
        exit 1
    fi

    # Get revision if not specified
    if [[ -z "${revision}" ]]; then
        revision=$(get_previous_revision "${environment}")
        if [[ -z "${revision}" ]]; then
            exit 1
        fi
    fi

    # Perform rollback
    if ! perform_rollback "${environment}" "${revision}"; then
        exit 1
    fi

    echo "Rollback completed successfully"
    exit 0
}

main "$@"