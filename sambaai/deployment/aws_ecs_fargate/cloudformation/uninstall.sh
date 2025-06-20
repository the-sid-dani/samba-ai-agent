#!/bin/bash

AWS_REGION="${AWS_REGION:-us-west-1}"

# Reference to consolidated config
CONFIG_FILE="sambaai_config.json"

# Get environment from config file
ENVIRONMENT=$(jq -r '.Environment' "$CONFIG_FILE")
if [ -z "$ENVIRONMENT" ] || [ "$ENVIRONMENT" == "null" ]; then
    echo "Missing Environment in $CONFIG_FILE. Please add the Environment field."
    exit 1
fi

# Try to get S3_BUCKET from config, fallback to default if not found
S3_BUCKET_FROM_CONFIG=$(jq -r '.S3Bucket // empty' "$CONFIG_FILE")
if [ -n "$S3_BUCKET_FROM_CONFIG" ]; then
    S3_BUCKET="$S3_BUCKET_FROM_CONFIG"
else
    S3_BUCKET="${S3_BUCKET:-sambaai-ecs-fargate-configs}"
fi

STACK_NAMES=(
  "${ENVIRONMENT}-sambaai-nginx-service"
  "${ENVIRONMENT}-sambaai-web-server-service"
  "${ENVIRONMENT}-sambaai-backend-background-server-service"
  "${ENVIRONMENT}-sambaai-backend-api-server-service"
  "${ENVIRONMENT}-sambaai-model-server-inference-service"
  "${ENVIRONMENT}-sambaai-model-server-indexing-service"
  "${ENVIRONMENT}-sambaai-vespaengine-service"
  "${ENVIRONMENT}-sambaai-redis-service"
  "${ENVIRONMENT}-sambaai-postgres-service"
  "${ENVIRONMENT}-sambaai-cluster"
  "${ENVIRONMENT}-sambaai-acm"
  "${ENVIRONMENT}-sambaai-efs"
  )

delete_stack() {
  local stack_name=$1

  if [ "$stack_name" == "${ENVIRONMENT}-sambaai-cluster" ]; then
      echo "Removing all objects and directories from the sambaai config s3 bucket."
      aws s3 rm "s3://${ENVIRONMENT}-${S3_BUCKET}" --recursive
      sleep 5
  fi

  echo "Checking if stack $stack_name exists..."
  if aws cloudformation describe-stacks --stack-name "$stack_name" --region "$AWS_REGION" > /dev/null 2>&1; then
  	echo "Deleting stack: $stack_name..."
  	aws cloudformation delete-stack \
		--stack-name "$stack_name" \
		--region "$AWS_REGION"
	
	echo "Waiting for stack $stack_name to be deleted..."
	aws cloudformation wait stack-delete-complete \
		--stack-name "$stack_name" \
		--region "$AWS_REGION"

	if [ $? -eq 0 ]; then
		echo "Stack $stack_name deleted successfully."
		sleep 10
	else
		echo "Failed to delete stack $stack_name. Exiting."
		exit 1
	fi
  else
	echo "Stack $stack_name does not exist, skipping."
	return 0
  fi	
}

for stack_name in "${STACK_NAMES[@]}"; do
  delete_stack "$stack_name"
done

echo "All stacks deleted successfully."
