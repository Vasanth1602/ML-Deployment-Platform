#!/bin/bash

###############################################################################
# Quick Reference Guide for Automated Deployment Framework Scripts
# Run this to see available commands and usage examples
###############################################################################

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Automated Deployment Framework - Scripts Quick Reference    ║${NC}"
echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo ""

echo -e "${BLUE}📁 Available Scripts:${NC}"
echo ""

echo -e "${YELLOW}1. setup_ec2.sh${NC} - Complete EC2 Instance Setup"
echo "   Purpose: Automate EC2 instance configuration for ML deployments"
echo "   Usage:   sudo bash scripts/setup_ec2.sh"
echo "   Features:"
echo "     • System package updates"
echo "     • Docker & Docker Compose installation"
echo "     • Firewall configuration"
echo "     • Swap space setup (2GB)"
echo "     • System optimization"
echo "     • Monitoring tools installation"
echo ""

echo -e "${YELLOW}2. install_docker.sh${NC} - Standalone Docker Installation"
echo "   Purpose: Install Docker on any Ubuntu-based system"
echo "   Usage:   sudo bash scripts/install_docker.sh"
echo "   Features:"
echo "     • Clean Docker installation"
echo "     • Docker daemon configuration"
echo "     • User group setup"
echo "     • Installation verification"
echo ""

echo -e "${YELLOW}3. cleanup_resources.sh${NC} - AWS Resources Cleanup"
echo "   Purpose: Clean up AWS resources and local Docker artifacts"
echo "   Usage:   bash scripts/cleanup_resources.sh"
echo "   Features:"
echo "     • Interactive menu system"
echo "     • EC2 instance termination"
echo "     • Security group deletion"
echo "     • Local Docker cleanup"
echo "     • Deployment logs cleanup"
echo ""

echo -e "${BLUE}📋 Common Workflows:${NC}"
echo ""

echo -e "${YELLOW}Initial EC2 Setup:${NC}"
echo "  1. SSH into EC2: ssh -i key.pem ubuntu@<ec2-ip>"
echo "  2. Upload script: scp -i key.pem setup_ec2.sh ubuntu@<ec2-ip>:~"
echo "  3. Run setup:    sudo bash setup_ec2.sh"
echo "  4. Logout/login for group changes"
echo ""

echo -e "${YELLOW}Manual Docker Installation:${NC}"
echo "  1. Download:     wget <repo-url>/scripts/install_docker.sh"
echo "  2. Make executable: chmod +x install_docker.sh"
echo "  3. Run:          sudo ./install_docker.sh"
echo ""

echo -e "${YELLOW}Resource Cleanup:${NC}"
echo "  1. Navigate:     cd scripts"
echo "  2. Make executable: chmod +x cleanup_resources.sh"
echo "  3. Run:          ./cleanup_resources.sh"
echo "  4. Select option from menu"
echo ""

echo -e "${BLUE}⚙️  Prerequisites:${NC}"
echo ""
echo "  setup_ec2.sh & install_docker.sh:"
echo "    • Ubuntu 20.04 LTS or later"
echo "    • Root/sudo access"
echo "    • Internet connection"
echo ""
echo "  cleanup_resources.sh:"
echo "    • AWS CLI installed (pip install awscli)"
echo "    • AWS credentials configured (aws configure)"
echo ""

echo -e "${BLUE}🔐 Make Scripts Executable:${NC}"
echo ""
echo "  chmod +x scripts/*.sh"
echo ""

echo -e "${BLUE}📖 Documentation:${NC}"
echo ""
echo "  For detailed documentation, see: scripts/README.md"
echo ""

echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
