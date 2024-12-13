#!/bin/bash

# Specification Management API Deployment Script
# Version: 1.0.0
# Description: Automates deployment to staging/production environments with health checks and rollback
# Dependencies: kubectl (v1.24+), kustomize (v4.5+), gcloud (latest)

set -euo pipefail

# Global variables
SCRIPT_DIR=$(dirname "${BASH_SOURCE[0]}")
PROJECT_ROOT=$(cd "${SCRIPT_DIR}/../.." && pwd)
DEPLOYMENT_TIMEOUT="300s"
HEALTH_CHECK_RETRIES=5
ROLLBACK_TIMEOUT="120s"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Print usage information
print_usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Deploys the Specification Management API to staging or production environment.

Options:
    -e, --environment    Target environment (staging|prod) [Required]
    -v, --version       Version tag to deploy [Required]
    -h, --help          Display this help message
    -f, --force         Skip confirmation prompts
    --dry-run          Simulate deployment without making changes

Environment-specific paths:
    Staging: ${PROJECT_ROOT}/infrastructure/kubernetes/overlays/staging
    Production: ${PROJECT_ROOT}/infrastructure/kubernetes/overlays/prod

Examples:
    Deploy to staging:
    $(basename "$0") -e staging -v 1.2.3

    Deploy to production:
    $(basename "$0") -e prod -v 1.2.3

Version tag format: Must follow semantic versioning (x.y.z)
EOF
}

# Log messages with timestamp and level
log() {
    local level=$1
    shift
    echo -e "[$(date +'%Y-%m-%d %H:%M:%S')] [${level}] $*"
}

# Validate environment argument
validate_environment() {
    local env=$1
    
    if [[ ! "$env" =~ ^(staging|prod)$ ]]; then
        log "ERROR" "Invalid environment: $env. Must be 'staging' or 'prod'"
        return 1
    }

    local env_path="${PROJECT_ROOT}/infrastructure/kubernetes/overlays/${env}"
    if [[ ! -d "$env_path" ]]; then
        log "ERROR" "Environment directory not found: $env_path"
        return 1
    }

    # Verify environment-specific configurations
    if [[ ! -f "${env_path}/kustomization.yaml" ]]; then
        log "ERROR" "Kustomization file not found for environment: $env"
        return 1
    }

    return 0
}

# Check required dependencies
check_dependencies() {
    local missing_deps=0

    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        log "ERROR" "kubectl is not installed"
        missing_deps=1
    else
        local kubectl_version
        kubectl_version=$(kubectl version --client -o json | jq -r '.clientVersion.gitVersion')
        if [[ ! "$kubectl_version" =~ v1\.2[4-9]\. ]]; then
            log "ERROR" "kubectl version $kubectl_version is not supported. Minimum required: v1.24"
            missing_deps=1
        fi
    fi

    # Check kustomize
    if ! command -v kustomize &> /dev/null; then
        log "ERROR" "kustomize is not installed"
        missing_deps=1
    fi

    # Check gcloud
    if ! command -v gcloud &> /dev/null; then
        log "ERROR" "gcloud is not installed"
        missing_deps=1
    fi

    # Verify GCP authentication
    if ! gcloud auth print-access-token &> /dev/null; then
        log "ERROR" "Not authenticated with GCP"
        missing_deps=1
    fi

    return $missing_deps
}

# Deploy application
deploy() {
    local environment=$1
    local version=$2
    local namespace="spec-mgmt-${environment}"
    local deployment_name="spec-mgmt-api"
    
    log "INFO" "Starting deployment to ${environment} environment with version ${version}"

    # Create deployment backup for potential rollback
    log "INFO" "Creating deployment backup"
    kubectl get deployment "${deployment_name}" -n "${namespace}" -o yaml > "/tmp/${deployment_name}-backup.yaml" || true

    # Update kustomization with new version
    log "INFO" "Updating kustomization with version ${version}"
    cd "${PROJECT_ROOT}/infrastructure/kubernetes/overlays/${environment}"
    kustomize edit set image "spec-mgmt-api=gcr.io/spec-mgmt/api:${version}"

    # Apply the configuration
    log "INFO" "Applying kustomize configuration"
    if ! kustomize build . | kubectl apply -f -; then
        log "ERROR" "Failed to apply configuration"
        perform_rollback "$environment" "$deployment_name" "$namespace"
        return 1
    fi

    # Wait for rollout
    log "INFO" "Waiting for rollout to complete"
    if ! kubectl rollout status deployment/"${deployment_name}" -n "${namespace}" --timeout="${DEPLOYMENT_TIMEOUT}"; then
        log "ERROR" "Deployment rollout failed"
        perform_rollback "$environment" "$deployment_name" "$namespace"
        return 1
    }

    # Perform health checks
    if ! perform_health_checks "$environment" "$deployment_name" "$namespace"; then
        log "ERROR" "Health checks failed"
        perform_rollback "$environment" "$deployment_name" "$namespace"
        return 1
    }

    log "SUCCESS" "Deployment completed successfully"
    return 0
}

# Perform health checks
perform_health_checks() {
    local environment=$1
    local deployment_name=$2
    local namespace=$3
    local retry_count=0

    while [ $retry_count -lt $HEALTH_CHECK_RETRIES ]; do
        log "INFO" "Performing health check attempt $((retry_count + 1))/${HEALTH_CHECK_RETRIES}"

        # Check pod status
        local ready_pods
        ready_pods=$(kubectl get deployment "${deployment_name}" -n "${namespace}" -o jsonpath='{.status.readyReplicas}')
        local desired_pods
        desired_pods=$(kubectl get deployment "${deployment_name}" -n "${namespace}" -o jsonpath='{.spec.replicas}')

        if [ "$ready_pods" != "$desired_pods" ]; then
            log "WARN" "Not all pods are ready: ${ready_pods}/${desired_pods}"
            ((retry_count++))
            sleep 10
            continue
        fi

        # Check endpoint health
        local pod_name
        pod_name=$(kubectl get pods -n "${namespace}" -l "app=${deployment_name}" -o jsonpath='{.items[0].metadata.name}')
        if ! kubectl exec "${pod_name}" -n "${namespace}" -- curl -s http://localhost:8000/health | grep -q "ok"; then
            log "WARN" "Health check endpoint not responding correctly"
            ((retry_count++))
            sleep 10
            continue
        fi

        log "INFO" "Health checks passed successfully"
        return 0
    done

    log "ERROR" "Health checks failed after ${HEALTH_CHECK_RETRIES} attempts"
    return 1
}

# Perform rollback
perform_rollback() {
    local environment=$1
    local deployment_name=$2
    local namespace=$3

    log "WARN" "Initiating rollback procedure"

    if [[ -f "/tmp/${deployment_name}-backup.yaml" ]]; then
        log "INFO" "Restoring from backup"
        if kubectl apply -f "/tmp/${deployment_name}-backup.yaml"; then
            log "INFO" "Waiting for rollback to complete"
            if kubectl rollout status deployment/"${deployment_name}" -n "${namespace}" --timeout="${ROLLBACK_TIMEOUT}"; then
                log "INFO" "Rollback completed successfully"
                return 0
            fi
        fi
    fi

    log "ERROR" "Rollback failed"
    return 1
}

# Main execution
main() {
    local environment=""
    local version=""
    local force=false
    local dry_run=false

    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -e|--environment)
                environment="$2"
                shift 2
                ;;
            -v|--version)
                version="$2"
                shift 2
                ;;
            -f|--force)
                force=true
                shift
                ;;
            --dry-run)
                dry_run=true
                shift
                ;;
            -h|--help)
                print_usage
                exit 0
                ;;
            *)
                log "ERROR" "Unknown option: $1"
                print_usage
                exit 1
                ;;
        esac
    done

    # Validate required arguments
    if [[ -z "$environment" || -z "$version" ]]; then
        log "ERROR" "Environment and version are required"
        print_usage
        exit 1
    fi

    # Validate environment
    if ! validate_environment "$environment"; then
        exit 1
    fi

    # Check dependencies
    if ! check_dependencies; then
        exit 1
    fi

    # Confirm deployment
    if [[ "$force" != true ]]; then
        read -rp "Deploy version ${version} to ${environment}? [y/N] " confirm
        if [[ ! "$confirm" =~ ^[yY]$ ]]; then
            log "INFO" "Deployment cancelled by user"
            exit 0
        fi
    fi

    # Execute deployment
    if [[ "$dry_run" == true ]]; then
        log "INFO" "Dry run mode - no changes will be made"
        exit 0
    fi

    if deploy "$environment" "$version"; then
        log "SUCCESS" "Deployment completed successfully"
        exit 0
    else
        log "ERROR" "Deployment failed"
        exit 1
    fi
}

# Execute main function
main "$@"