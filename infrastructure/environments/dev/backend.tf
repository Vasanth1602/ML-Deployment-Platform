terraform {
  backend "s3" {
    bucket         = "ml-deploy-tf-state-051602877351"
    key            = "dev/terraform.tfstate"
    region         = "ap-south-1"
    dynamodb_table = "ml-deploy-tf-lock"
    encrypt        = true
  }
}