#!/bin/bash

###############################################################################
# Docker Installation Script
# Standalone script to install Docker on Ubuntu-based systems
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

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    log_error "Please run as root (use sudo)"
    exit 1
fi

log_info "Docker Installation Script"
echo "=================================="

# Check if Docker is already installed
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version)
    log_warn "Docker is already installed: $DOCKER_VERSION"
    read -p "Do you want to reinstall? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Installation cancelled"
        exit 0
    fi
    log_step "Removing existing Docker installation..."
    apt-get remove -y docker docker-engine docker.io containerd runc || true
fi

# Step 1: Update package index
log_step "Updating package index..."
apt-get update -y

# Step 2: Install prerequisites
log_step "Installing prerequisites..."
apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# Step 3: Add Docker's official GPG key
log_step "Adding Docker's official GPG key..."
mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

# Step 4: Set up Docker repository
log_step "Setting up Docker repository..."
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# Step 5: Update package index again
log_step "Updating package index with Docker repository..."
apt-get update -y

# Step 6: Install Docker Engine
log_step "Installing Docker Engine, CLI, and plugins..."
apt-get install -y \
    docker-ce \
    docker-ce-cli \
    containerd.io \
    docker-buildx-plugin \
    docker-compose-plugin

# Step 7: Start and enable Docker service
log_step "Starting and enabling Docker service..."
systemctl start docker
systemctl enable docker

# Step 8: Add current user to docker group (if not root)
if [ -n "$SUDO_USER" ]; then
    log_step "Adding user '$SUDO_USER' to docker group..."
    usermod -aG docker $SUDO_USER
    log_warn "Please log out and log back in for group changes to take effect"
fi

# Add ubuntu user to docker group (for EC2 instances)
if id "ubuntu" &>/dev/null; then
    log_step "Adding user 'ubuntu' to docker group..."
    usermod -aG docker ubuntu
fi

# Step 9: Verify installation
log_step "Verifying Docker installation..."
docker --version
docker compose version

# Step 10: Test Docker with hello-world
log_step "Testing Docker with hello-world container..."
if docker run --rm hello-world &> /dev/null; then
    log_info "Docker test successful!"
else
    log_warn "Docker test failed, but installation appears complete"
fi

# Display Docker info
log_info "Docker installation complete!"
echo "=================================="
docker --version
docker compose version
echo "=================================="

# Optional: Configure Docker daemon
log_step "Configuring Docker daemon..."
mkdir -p /etc/docker
cat > /etc/docker/daemon.json << EOF
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "storage-driver": "overlay2"
}
EOF

# Restart Docker to apply configuration
log_step "Restarting Docker service..."
systemctl restart docker

log_info "Docker is ready to use!"
log_info "Run 'docker ps' to verify Docker is working"

# Display next steps
echo ""
echo "=================================="
echo "Next Steps:"
echo "1. Log out and log back in (for group changes)"
echo "2. Run 'docker ps' to verify Docker is working"
echo "3. Run 'docker run hello-world' to test"
echo "=================================="

exit 0
