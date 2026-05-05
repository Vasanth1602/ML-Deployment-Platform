output "state_bucket_name" {
  description = "S3 bucket name — copy this into all backend.tf files"
  value       = aws_s3_bucket.tf_state.bucket
}

output "state_bucket_arn" {
  value = aws_s3_bucket.tf_state.arn
}

output "lock_table_name" {
  description = "DynamoDB table name — copy this into all backend.tf files"
  value       = aws_dynamodb_table.tf_lock.name
}