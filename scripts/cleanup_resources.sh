#!/bin/bash

###############################################################################
# AWS Resources Cleanup Script
# Cleans up EC2 instances, security groups, and other resources created by
# the Automated Deployment Framework
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    log_error "AWS CLI is not installed. Please install it first."
    echo "Install with: pip install awscli"
    exit 1
fi

# Check if AWS credentials are configured
if ! aws sts get-caller-identity &> /dev/null; then
    log_error "AWS credentials are not configured properly"
    echo "Configure with: aws configure"
    exit 1
fi

log_info "AWS Resources Cleanup Script"
echo "=================================="

# Get AWS region from environment or use default
AWS_REGION=${AWS_REGION:-us-east-1}
log_info "Using AWS region: $AWS_REGION"

# Tag used to identify resources managed by the framework
MANAGED_TAG="ManagedBy=AutomatedDeploymentFramework"

# Function to list resources
list_managed_instances() {
    log_step "Listing managed EC2 instances..."
    aws ec2 describe-instances \
        --region $AWS_REGION \
        --filters "Name=tag:ManagedBy,Values=AutomatedDeploymentFramework" \
                  "Name=instance-state-name,Values=running,stopped" \
        --query 'Reservations[*].Instances[*].[InstanceId,State.Name,Tags[?Key==`Name`].Value|[0],PublicIpAddress]' \
        --output table
}

# Function to terminate instances
terminate_instances() {
    log_step "Finding instances to terminate..."
    
    INSTANCE_IDS=$(aws ec2 describe-instances \
        --region $AWS_REGION \
        --filters "Name=tag:ManagedBy,Values=AutomatedDeploymentFramework" \
                  "Name=instance-state-name,Values=running,stopped" \
        --query 'Reservations[*].Instances[*].InstanceId' \
        --output text)
    
    if [ -z "$INSTANCE_IDS" ]; then
        log_info "No managed instances found"
        return
    fi
    
    echo "Found instances: $INSTANCE_IDS"
    read -p "Terminate these instances? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_step "Terminating instances..."
        aws ec2 terminate-instances \
            --region $AWS_REGION \
            --instance-ids $INSTANCE_IDS
        log_info "Instances termination initiated"
        
        log_step "Waiting for instances to terminate..."
        aws ec2 wait instance-terminated \
            --region $AWS_REGION \
            --instance-ids $INSTANCE_IDS
        log_info "All instances terminated"
    else
        log_info "Instance termination cancelled"
    fi
}

# Function to delete security groups
delete_security_groups() {
    log_step "Finding security groups to delete..."
    
    SG_IDS=$(aws ec2 describe-security-groups \
        --region $AWS_REGION \
        --filters "Name=tag:ManagedBy,Values=AutomatedDeploymentFramework" \
        --query 'SecurityGroups[*].[GroupId,GroupName]' \
        --output text)
    
    if [ -z "$SG_IDS" ]; then
        log_info "No managed security groups found"
        return
    fi
    
    echo "Found security groups:"
    echo "$SG_IDS"
    read -p "Delete these security groups? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        while IFS=$'\t' read -r SG_ID SG_NAME; do
            log_step "Deleting security group: $SG_NAME ($SG_ID)"
            
            # Wait a bit to ensure instances are fully terminated
            sleep 5
            
            # Try to delete, ignore errors if dependencies exist
            if aws ec2 delete-security-group \
                --region $AWS_REGION \
                --group-id $SG_ID 2>/dev/null; then
                log_info "Deleted security group: $SG_ID"
            else
                log_warn "Could not delete security group: $SG_ID (may have dependencies)"
            fi
        done <<< "$SG_IDS"
    else
        log_info "Security group deletion cancelled"
    fi
}

# Function to clean up Docker resources on local machine
cleanup_local_docker() {
    log_step "Cleaning up local Docker resources..."
    
    if ! command -v docker &> /dev/null; then
        log_warn "Docker is not installed locally"
        return
    fi
    
    read -p "Clean up local Docker resources? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_step "Removing stopped containers..."
        docker container prune -f || true
        
        log_step "Removing unused images..."
        docker image prune -a -f || true
        
        log_step "Removing unused volumes..."
        docker volume prune -f || true
        
        log_step "Removing unused networks..."
        docker network prune -f || true
        
        log_info "Docker cleanup complete"
    else
        log_info "Docker cleanup cancelled"
    fi
}

# Function to clean up deployment logs
cleanup_logs() {
    log_step "Cleaning up deployment logs..."
    
    if [ -d "../deployment_logs" ]; then
        LOG_COUNT=$(find ../deployment_logs -type f -name "*.log" | wc -l)
        
        if [ $LOG_COUNT -gt 0 ]; then
            echo "Found $LOG_COUNT log files"
            read -p "Delete deployment logs? (y/N): " -n 1 -r
            echo
            
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                rm -rf ../deployment_logs/*.log
                log_info "Deployment logs deleted"
            else
                log_info "Log cleanup cancelled"
            fi
        else
            log_info "No deployment logs found"
        fi
    else
        log_info "No deployment_logs directory found"
    fi
}

# Main menu
show_menu() {
    echo ""
    echo "=================================="
    echo "Cleanup Options:"
    echo "1. List managed resources"
    echo "2. Terminate EC2 instances"
    echo "3. Delete security groups"
    echo "4. Clean up local Docker"
    echo "5. Clean up deployment logs"
    echo "6. Full cleanup (all of the above)"
    echo "0. Exit"
    echo "=================================="
    read -p "Select option: " choice
    
    case $choice in
        1)
            list_managed_instances
            show_menu
            ;;
        2)
            terminate_instances
            show_menu
            ;;
        3)
            delete_security_groups
            show_menu
            ;;
        4)
            cleanup_local_docker
            show_menu
            ;;
        5)
            cleanup_logs
            show_menu
            ;;
        6)
            log_warn "This will clean up ALL resources!"
            read -p "Are you sure? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                terminate_instances
                delete_security_groups
                cleanup_local_docker
                cleanup_logs
                log_info "Full cleanup complete!"
            else
                log_info "Full cleanup cancelled"
            fi
            ;;
        0)
            log_info "Exiting cleanup script"
            exit 0
            ;;
        *)
            log_error "Invalid option"
            show_menu
            ;;
    esac
}

# Start the script
show_menu
