# AWS CLI Serverless Event Pipeline (SNS → Lambda → DynamoDB)

## Overview

Event-driven serverless pipeline built and operated using the AWS CLI:

- SNS ingests events
- Lambda processes messages
- DynamoDB (`PAY_PER_REQUEST`) persists events with TTL-based retention
- CloudWatch Logs provides observability

## Architecture

```text
SNS Topic → Lambda (subscription) → DynamoDB
                    ↳ CloudWatch Logs
```

## Repository Contents

```text
.
├── src/lambda_function.py           # Lambda handler: writes each SNS record to DynamoDB
├── lambda.zip                       # Packaged handler (same code as src/)
└── scripts/
    ├── lambda-trust-policy.json     # Trust policy: lets Lambda assume the role
    └── ddb-write-policy.json        # Inline policy: write to the events table only
```

Each stored item contains `pk` (`evt#<SNS MessageId>`), `received_at`, `ttl`, `topic_arn`, `subject` and `message`.

## Design Decisions

- Lambda kept **outside a VPC** to avoid NAT Gateway / interface endpoint hourly costs and reduce operational complexity.
- **Least-privilege IAM** for the Lambda execution role: write access to a single DynamoDB table, plus the AWS managed `AWSLambdaBasicExecutionRole` for CloudWatch Logs.
- **On-demand DynamoDB** to avoid capacity planning and keep costs low for low/variable traffic.
- **TTL enabled** on the `ttl` attribute to enforce retention (default 7 days, `TTL_DAYS` env var) and limit storage growth.

## How to Deploy (AWS CLI)

Reference commands for rebuilding the pipeline. Region and names match the ones used in this lab; replace `<ACCOUNT_ID>` with your own AWS account ID, including in `scripts/ddb-write-policy.json`.

```bash
REGION=eu-central-1
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
TABLE=cli-sns-lambda-ddb-dev-events
ROLE=cli-sns-lambda-ddb-dev-role
FUNC=cli-sns-lambda-ddb-dev-handler
TOPIC=cli-sns-lambda-ddb-dev-topic
```

1. Create the DynamoDB table and enable TTL:

```bash
aws dynamodb create-table --region $REGION --table-name $TABLE \
  --attribute-definitions AttributeName=pk,AttributeType=S \
  --key-schema AttributeName=pk,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

```bash
aws dynamodb update-time-to-live --region $REGION --table-name $TABLE \
  --time-to-live-specification "Enabled=true,AttributeName=ttl"
```

2. Create the IAM role and attach permissions:

```bash
aws iam create-role --role-name $ROLE \
  --assume-role-policy-document file://scripts/lambda-trust-policy.json
```

```bash
aws iam attach-role-policy --role-name $ROLE \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
```

```bash
aws iam put-role-policy --role-name $ROLE --policy-name ddb-write \
  --policy-document file://scripts/ddb-write-policy.json
```

3. Package and create the Lambda function:

```bash
(cd src && zip ../lambda.zip lambda_function.py)
```

```bash
aws lambda create-function --region $REGION --function-name $FUNC \
  --runtime python3.12 --handler lambda_function.lambda_handler \
  --role arn:aws:iam::$ACCOUNT_ID:role/$ROLE \
  --zip-file fileb://lambda.zip \
  --environment "Variables={TABLE_NAME=$TABLE,TTL_DAYS=7}"
```

4. Create the SNS topic, allow it to invoke Lambda, and subscribe:

```bash
TOPIC_ARN=$(aws sns create-topic --region $REGION --name $TOPIC --query TopicArn --output text)
```

```bash
aws lambda add-permission --region $REGION --function-name $FUNC \
  --statement-id sns-invoke --action lambda:InvokeFunction \
  --principal sns.amazonaws.com --source-arn $TOPIC_ARN
```

```bash
aws sns subscribe --region $REGION --topic-arn $TOPIC_ARN \
  --protocol lambda --notification-endpoint arn:aws:lambda:$REGION:$ACCOUNT_ID:function:$FUNC
```

## Validation

End-to-end test confirmed:

- SNS publish triggers Lambda
- Lambda writes an item to DynamoDB with `pk`, message payload, and TTL

```bash
aws sns publish --region $REGION --topic-arn $TOPIC_ARN \
  --subject "test" --message '{"hello":"world"}'
```

```bash
aws dynamodb scan --region $REGION --table-name $TABLE --max-items 5
```

```bash
aws logs tail /aws/lambda/$FUNC --region $REGION --since 10m
```

## Cleanup

```bash
aws sns delete-topic --region $REGION --topic-arn $TOPIC_ARN
```

```bash
aws lambda delete-function --region $REGION --function-name $FUNC
```

```bash
aws iam delete-role-policy --role-name $ROLE --policy-name ddb-write
```

```bash
aws iam detach-role-policy --role-name $ROLE \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
```

```bash
aws iam delete-role --role-name $ROLE
```

```bash
aws dynamodb delete-table --region $REGION --table-name $TABLE
```

## Next Improvements

- Add a CloudWatch Alarm on Lambda errors with SNS alerting
- Add a DLQ strategy (SQS) for failed event processing
- Add structured metrics (EMF) for observability
