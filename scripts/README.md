# Scripts Directory

This directory contains shell scripts for automating various deployment and maintenance tasks.

## Available Scripts

### 1. setup_ec2.sh
**Purpose:** Complete EC2 instance setup and optimization for ML deployments

**Features:**
- System package updates
- Docker installation and configuration
- Docker Compose installation
- Firewall configuration (UFW)
- Swap space setup (for t2.micro instances)
- System optimization
- Monitoring tools installation

**Usage:**
```bash
# On EC2 instance
sudo bash setup_ec2.sh
```

**What it does:**
- ✅ Updates and upgrades system packages
- ✅ Installs Docker Engine and Docker Compose
- ✅ Configures firewall rules (SSH, HTTP, HTTPS, custom ports)
- ✅ Creates 2GB swap space for memory optimization
- ✅ Optimizes kernel parameters for Docker
- ✅ Installs monitoring tools (htop, sysstat, iotop)
- ✅ Creates deployment directory structure

---

### 2. install_docker.sh
**Purpose:** Standalone Docker installation script

**Features:**
- Clean Docker installation
- User group configuration
- Docker daemon optimization
- Installation verification

**Usage:**
```bash
# On any Ubuntu-based system
sudo bash install_docker.sh
```

**What it does:**
- ✅ Checks for existing Docker installation
- ✅ Adds Docker's official GPG key and repository
- ✅ Installs Docker Engine, CLI, and plugins
- ✅ Configures Docker daemon with logging limits
- ✅ Adds users to docker group
- ✅ Tests installation with hello-world container

---

### 3. cleanup_resources.sh
**Purpose:** Clean up AWS resources and local Docker artifacts

**Features:**
- Interactive menu system
- Safe resource deletion with confirmations
- AWS resource cleanup
- Local Docker cleanup
- Deployment logs cleanup

**Usage:**
```bash
# Requires AWS CLI configured
bash cleanup_resources.sh
```

**What it does:**
- ✅ Lists all managed EC2 instances
- ✅ Terminates EC2 instances with confirmation
- ✅ Deletes security groups
- ✅ Cleans up local Docker resources
- ✅ Removes deployment logs
- ✅ Full cleanup option

**Menu Options:**
1. List managed resources
2. Terminate EC2 instances
3. Delete security groups
4. Clean up local Docker
5. Clean up deployment logs
6. Full cleanup (all of the above)
0. Exit

---

## Prerequisites

### For setup_ec2.sh and install_docker.sh:
- Ubuntu 20.04 LTS or later
- Root/sudo access
- Internet connection

### For cleanup_resources.sh:
- AWS CLI installed (`pip install awscli`)
- AWS credentials configured (`aws configure`)
- Bash shell

---

## Usage Examples

### Initial EC2 Setup
```bash
# SSH into your EC2 instance
ssh -i your-key.pem ubuntu@your-ec2-ip

# Upload and run setup script
scp -i your-key.pem setup_ec2.sh ubuntu@your-ec2-ip:~
ssh -i your-key.pem ubuntu@your-ec2-ip
sudo bash setup_ec2.sh

# Log out and back in for group changes
exit
ssh -i your-key.pem ubuntu@your-ec2-ip

# Verify Docker
docker ps
```

### Standalone Docker Installation
```bash
# Download script
wget https://your-repo/scripts/install_docker.sh

# Make executable and run
chmod +x install_docker.sh
sudo ./install_docker.sh

# Verify installation
docker --version
docker run hello-world
```

### Resource Cleanup
```bash
# Navigate to scripts directory
cd scripts

# Make executable
chmod +x cleanup_resources.sh

# Run cleanup
./cleanup_resources.sh

# Select option from menu
# Option 6 for full cleanup
```

---

## Script Permissions

Make scripts executable:
```bash
chmod +x scripts/*.sh
```

Or individually:
```bash
chmod +x scripts/setup_ec2.sh
chmod +x scripts/install_docker.sh
chmod +x scripts/cleanup_resources.sh
```

---

## Safety Features

### setup_ec2.sh
- ✅ Checks for root privileges
- ✅ Verifies existing installations before reinstalling
- ✅ Creates backups of configuration files
- ✅ Provides detailed logging

### install_docker.sh
- ✅ Confirms before reinstalling Docker
- ✅ Tests installation before completing
- ✅ Provides rollback information
- ✅ Step-by-step progress logging

### cleanup_resources.sh
- ✅ Interactive confirmations for all deletions
- ✅ Lists resources before deletion
- ✅ Handles dependencies gracefully
- ✅ Provides undo information where possible

---

## Integration with Framework

These scripts complement the Python-based deployment framework:

- **setup_ec2.sh** - Can be used for manual EC2 setup or as a reference
- **install_docker.sh** - Standalone alternative to Python Docker manager
- **cleanup_resources.sh** - Batch cleanup tool for development/testing

The Python framework handles these tasks automatically, but scripts are useful for:
- Manual troubleshooting
- Batch operations
- Custom deployments
- Learning and reference

---

## Troubleshooting

### Script won't run
```bash
# Check permissions
ls -l scripts/

# Make executable
chmod +x scripts/script_name.sh

# Check line endings (if copied from Windows)
dos2unix scripts/script_name.sh
```

### Docker installation fails
```bash
# Check system compatibility
lsb_release -a

# Ensure system is updated
sudo apt-get update
sudo apt-get upgrade

# Check for conflicting packages
dpkg -l | grep docker
```

### AWS cleanup fails
```bash
# Verify AWS CLI installation
aws --version

# Check credentials
aws sts get-caller-identity

# Verify region
echo $AWS_REGION
```

---

## Future Enhancements

Planned scripts for future versions:

- `backup_deployment.sh` - Backup deployment configurations
- `monitor_resources.sh` - Real-time resource monitoring
- `scale_deployment.sh` - Scale deployments across multiple instances
- `setup_ssl.sh` - Configure SSL/HTTPS certificates
- `health_check.sh` - Comprehensive health checking
- `rollback_deployment.sh` - Rollback to previous deployment

---

## Contributing

When adding new scripts:
1. Follow the existing naming convention
2. Include comprehensive comments
3. Add error handling
4. Provide usage examples
5. Update this README

---

## License

These scripts are part of the Automated Deployment Framework and follow the same license.
