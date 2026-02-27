"""
AWS EC2 Manager for the Automated Deployment Framework.
Handles EC2 instance creation, management, and security group configuration.
"""

import boto3
import logging
import time
from typing import Dict, Optional, List
from botocore.exceptions import ClientError

from ...config import config

logger = logging.getLogger(__name__)


class AWSManager:
    """Manages AWS EC2 instances and related resources."""
    
    def __init__(self):
        """Initialize AWS Manager with boto3 clients."""
        self.ec2_client = boto3.client(
            'ec2',
            aws_access_key_id=config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
            region_name=config.AWS_REGION
        )
        
        self.ec2_resource = boto3.resource(
            'ec2',
            aws_access_key_id=config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
            region_name=config.AWS_REGION
        )
        
        logger.info(f"AWS Manager initialized for region: {config.AWS_REGION}")
    
    def create_or_get_security_group(self, group_name: str = None) -> str:
        """
        Create or get existing security group.
        
        Args:
            group_name: Security group name (uses config default if not provided)
            
        Returns:
            Security group ID
        """
        if group_name is None:
            group_name = config.SECURITY_GROUP_NAME
        
        try:
            # Check if security group already exists
            response = self.ec2_client.describe_security_groups(
                Filters=[{'Name': 'group-name', 'Values': [group_name]}]
            )
            
            if response['SecurityGroups']:
                sg_id = response['SecurityGroups'][0]['GroupId']
                logger.info(f"Using existing security group: {sg_id}")
                return sg_id
            
            # Create new security group
            logger.info(f"Creating security group: {group_name}")
            response = self.ec2_client.create_security_group(
                GroupName=group_name,
                Description='Security group for ML application deployment'
            )
            
            sg_id = response['GroupId']
            logger.info(f"Created security group: {sg_id}")
            
            # Add ingress rules
            self._configure_security_group_rules(sg_id)
            
            return sg_id
            
        except ClientError as e:
            logger.error(f"Error creating security group: {str(e)}")
            raise
    
    def _configure_security_group_rules(self, sg_id: str):
        """
        Configure security group ingress rules.
        
        Args:
            sg_id: Security group ID
        """
        try:
            logger.info(f"Configuring security group rules for {sg_id}")
            
            self.ec2_client.authorize_security_group_ingress(
                GroupId=sg_id,
                IpPermissions=config.get_security_group_rules()
            )
            
            logger.info("Security group rules configured successfully")
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'InvalidPermission.Duplicate':
                logger.info("Security group rules already exist")
            else:
                logger.error(f"Error configuring security group rules: {str(e)}")
                raise
    
    def create_instance(self, 
                       instance_name: str,
                       instance_type: str = None,
                       ami_id: str = None,
                       key_name: str = None,
                       security_group_id: str = None) -> Dict:
        """
        Create a new EC2 instance.
        
        Args:
            instance_name: Name tag for the instance
            instance_type: EC2 instance type (uses config default if not provided)
            ami_id: AMI ID (uses config default if not provided)
            key_name: Key pair name (uses config default if not provided)
            security_group_id: Security group ID (creates new if not provided)
            
        Returns:
            Dictionary with instance details
        """
        if instance_type is None:
            instance_type = config.EC2_INSTANCE_TYPE
        
        if ami_id is None:
            ami_id = config.EC2_AMI_ID
        
        if key_name is None:
            key_name = config.AWS_KEY_PAIR_NAME
        
        if security_group_id is None:
            security_group_id = self.create_or_get_security_group()
        
        try:
            logger.info(f"Creating EC2 instance: {instance_name}")
            logger.info(f"Instance type: {instance_type}, AMI: {ami_id}")
            
            # User data script to update system on first boot
            user_data_script = """#!/bin/bash
            sudo apt-get update
            sudo apt-get upgrade -y
            """
            
            instances = self.ec2_resource.create_instances(
                ImageId=ami_id,
                InstanceType=instance_type,
                KeyName=key_name,
                SecurityGroupIds=[security_group_id],
                MinCount=1,
                MaxCount=1,
                UserData=user_data_script,
                BlockDeviceMappings=[
                    {
                        'DeviceName': '/dev/sda1',
                        'Ebs': {
                            'VolumeSize': config.EC2_VOLUME_SIZE,
                            'VolumeType': 'gp3',
                            'DeleteOnTermination': True
                        }
                    }
                ],
                TagSpecifications=[
                    {
                        'ResourceType': 'instance',
                        'Tags': [
                            {'Key': 'Name', 'Value': instance_name},
                            {'Key': 'ManagedBy', 'Value': 'AutomatedDeploymentFramework'}
                        ]
                    }
                ]
            )
            
            instance = instances[0]
            instance_id = instance.id
            
            logger.info(f"Instance created: {instance_id}")
            logger.info("Waiting for instance to be running...")
            
            # Wait for instance to be running
            instance.wait_until_running()
            instance.reload()
            
            public_ip = instance.public_ip_address
            private_ip = instance.private_ip_address
            
            logger.info(f"Instance is running. Public IP: {public_ip}")
            
            return {
                'instance_id': instance_id,
                'public_ip': public_ip,
                'private_ip': private_ip,
                'instance_type': instance_type,
                'state': instance.state['Name'],
                'security_group_id': security_group_id
            }
            
        except ClientError as e:
            logger.error(f"Error creating EC2 instance: {str(e)}")
            raise
    
    def get_instance_status(self, instance_id: str) -> Dict:
        """
        Get current status of an EC2 instance.
        
        Args:
            instance_id: EC2 instance ID
            
        Returns:
            Dictionary with instance status
        """
        try:
            instance = self.ec2_resource.Instance(instance_id)
            instance.reload()
            
            return {
                'instance_id': instance_id,
                'state': instance.state['Name'],
                'public_ip': instance.public_ip_address,
                'private_ip': instance.private_ip_address,
                'instance_type': instance.instance_type
            }
            
        except ClientError as e:
            logger.error(f"Error getting instance status: {str(e)}")
            raise
    
    def terminate_instance(self, instance_id: str) -> bool:
        """
        Terminate an EC2 instance.
        
        Args:
            instance_id: EC2 instance ID
            
        Returns:
            True if termination initiated successfully
        """
        try:
            logger.info(f"Terminating instance: {instance_id}")
            
            instance = self.ec2_resource.Instance(instance_id)
            instance.terminate()
            
            logger.info(f"Instance {instance_id} termination initiated")
            return True
            
        except ClientError as e:
            logger.error(f"Error terminating instance: {str(e)}")
            raise
    
    def stop_instance(self, instance_id: str) -> bool:
        """
        Stop an EC2 instance.
        
        Args:
            instance_id: EC2 instance ID
            
        Returns:
            True if stop initiated successfully
        """
        try:
            logger.info(f"Stopping instance: {instance_id}")
            
            instance = self.ec2_resource.Instance(instance_id)
            instance.stop()
            
            logger.info(f"Instance {instance_id} stop initiated")
            return True
            
        except ClientError as e:
            logger.error(f"Error stopping instance: {str(e)}")
            raise
    
    def start_instance(self, instance_id: str) -> bool:
        """
        Start a stopped EC2 instance.
        
        Args:
            instance_id: EC2 instance ID
            
        Returns:
            True if start initiated successfully
        """
        try:
            logger.info(f"Starting instance: {instance_id}")
            
            instance = self.ec2_resource.Instance(instance_id)
            instance.start()
            
            logger.info(f"Instance {instance_id} start initiated")
            return True
            
        except ClientError as e:
            logger.error(f"Error starting instance: {str(e)}")
            raise
    
    def list_instances(self, filters: List[Dict] = None) -> List[Dict]:
        """
        List EC2 instances with optional filters.
        
        Args:
            filters: List of filters for instance search
            
        Returns:
            List of instance details
        """
        try:
            if filters is None:
                filters = [
                    {
                        'Name': 'tag:ManagedBy',
                        'Values': ['AutomatedDeploymentFramework']
                    }
                ]
            
            instances = self.ec2_resource.instances.filter(Filters=filters)
            
            instance_list = []
            for instance in instances:
                instance_list.append({
                    'instance_id': instance.id,
                    'state': instance.state['Name'],
                    'public_ip': instance.public_ip_address,
                    'private_ip': instance.private_ip_address,
                    'instance_type': instance.instance_type,
                    'launch_time': instance.launch_time.isoformat() if instance.launch_time else None
                })
            
            return instance_list
            
        except ClientError as e:
            logger.error(f"Error listing instances: {str(e)}")
            raise
