# AWS CLI Serverless Event Pipeline (SNS → Lambda → DynamoDB)

## Overview
Event-driven serverless pipeline built and operated using AWS CLI:
- SNS ingests events
- Lambda processes messages
- DynamoDB (PAY_PER_REQUEST) persists events with TTL-based retention
- CloudWatch Logs provides observability

## Architecture
SNS Topic → Lambda (subscription) → DynamoDB  
                              ↳ CloudWatch Logs

## Design decisions
- Lambda kept **outside VPC** to avoid NAT Gateway / interface endpoint hourly costs and reduce operational complexity.
- **Least privilege IAM** for the Lambda execution role (write to a single DynamoDB table + logging).
- **On-demand DynamoDB** to prevent capacity planning and control spend for low/variable traffic.
- **TTL enabled** to enforce retention and minimize storage growth.

## Validation
End-to-end test confirmed:
- SNS publish triggers Lambda
- Lambda writes item to DynamoDB with `pk`, message payload, and TTL

## Next improvements
- Add CloudWatch Alarm on Lambda errors with SNS alerting
- Add DLQ strategy (SQS) for failed event processing
- Add structured metrics (EMF) for observability

