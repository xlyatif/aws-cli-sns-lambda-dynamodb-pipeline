import json, os, time, hashlib
import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])
ttl_days = int(os.environ.get("TTL_DAYS", "7"))

def _stable_id(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def lambda_handler(event, context):
    now = int(time.time())
    ttl = now + ttl_days * 24 * 60 * 60
    written = 0

    for r in event.get("Records", []):
        sns = r.get("Sns", {})
        msg = sns.get("Message", "")
        msg_id = sns.get("MessageId", "") or _stable_id(msg)

        table.put_item(Item={
            "pk": f"evt#{msg_id}",
            "received_at": now,
            "ttl": ttl,
            "topic_arn": sns.get("TopicArn", ""),
            "subject": sns.get("Subject", ""),
            "message": msg
        })
        written += 1

    print(json.dumps({"status": "ok", "written": written}))
    return {"statusCode": 200, "written": written}
