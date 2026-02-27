import boto3

ec2 = boto3.client("ec2", region_name="ap-south-1")
print(ec2.describe_regions())
