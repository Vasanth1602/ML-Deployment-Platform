#!/bin/bash

###############################################################################
# EC2 Instance Setup Script
# This script automates the initial setup of an EC2 instance for ML deployment
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    log_error "Please run as root (use sudo)"
    exit 1
fi

log_info "Starting EC2 instance setup..."

# Update system packages
log_info "Updating system packages..."
apt-get update -y
apt-get upgrade -y

# Install essential packages
log_info "Installing essential packages..."
apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    wget \
    vim \
    htop \
    net-tools \
    python3 \
    python3-pip

# Install Docker
log_info "Installing Docker..."
if command -v docker &> /dev/null; then
    log_warn "Docker is already installed"
    docker --version
else
    # Add Docker's official GPG key
    mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    
    # Set up Docker repository
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # Install Docker Engine
    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    
    # Start and enable Docker
    systemctl start docker
    systemctl enable docker
    
    log_info "Docker installed successfully"
    docker --version
fi

# Add ubuntu user to docker group
log_info "Adding ubuntu user to docker group..."
usermod -aG docker ubuntu

# Install Docker Compose (standalone)
log_info "Installing Docker Compose..."
if command -v docker-compose &> /dev/null; then
    log_warn "Docker Compose is already installed"
    docker-compose --version
else
    DOCKER_COMPOSE_VERSION="v2.24.0"
    curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    log_info "Docker Compose installed successfully"
    docker-compose --version
fi

# Configure firewall (UFW)
log_info "Configuring firewall..."
if command -v ufw &> /dev/null; then
    ufw --force enable
    ufw allow 22/tcp      # SSH
    ufw allow 80/tcp      # HTTP
    ufw allow 443/tcp     # HTTPS
    ufw allow 8000/tcp    # Application port
    ufw status
    log_info "Firewall configured"
else
    log_warn "UFW not available, skipping firewall configuration"
fi

# Set up swap space (for t2.micro instances with limited RAM)
log_info "Setting up swap space..."
if [ ! -f /swapfile ]; then
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' | tee -a /etc/fstab
    log_info "Swap space created (2GB)"
else
    log_warn "Swap file already exists"
fi

# Optimize system settings
log_info "Optimizing system settings..."
cat >> /etc/sysctl.conf << EOF

# Optimizations for Docker
vm.swappiness=10
vm.vfs_cache_pressure=50
net.core.somaxconn=1024
net.ipv4.tcp_max_syn_backlog=2048
EOF

sysctl -p

# Create deployment directory
log_info "Creating deployment directory..."
mkdir -p /opt/deployments
chown ubuntu:ubuntu /opt/deployments

# Install monitoring tools
log_info "Installing monitoring tools..."
apt-get install -y \
    sysstat \
    iotop \
    iftop

# Clean up
log_info "Cleaning up..."
apt-get autoremove -y
apt-get clean

# Display system information
log_info "Setup complete! System information:"
echo "=================================="
echo "OS: $(lsb_release -d | cut -f2)"
echo "Kernel: $(uname -r)"
echo "Docker: $(docker --version)"
echo "Docker Compose: $(docker-compose --version)"
echo "Python: $(python3 --version)"
echo "Git: $(git --version)"
echo "=================================="

log_info "EC2 instance is ready for ML deployments!"
log_warn "Please log out and log back in for docker group changes to take effect"

exit 0
