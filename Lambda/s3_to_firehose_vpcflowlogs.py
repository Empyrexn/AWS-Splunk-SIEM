import boto3
import os
import gzip
import io
import re
import logging
s3 = boto3.client('s3')
firehose = boto3.client('firehose')
FIREHOSE_STREAM = os.environ['FIREHOSE_STREAM']
MAX_RECORDS = 450
logger = logging.getLogger()
logger.setLevel(logging.INFO)
# Remove ISO timestamp prefixes like "2025-07-21T04:15:27.000Z"
ISO_PREFIX = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z\s+')
def read_s3_object(bucket, key):
    """Read S3 object (auto-decompress if .gz)."""
    obj = s3.get_object(Bucket=bucket, Key=key)
    body = obj['Body'].read()
    if key.endswith('.gz'):
        with gzip.GzipFile(fileobj=io.BytesIO(body)) as gz:
            return gz.read().decode('utf-8', errors='replace')
    return body.decode('utf-8', errors='replace')
def sanitize_vpcflow_line(line):
    """Remove leading ISO timestamp and normalize whitespace."""
    line = ISO_PREFIX.sub('', line.strip())
    return re.sub(r'\s+', ' ', line)
def put_records_raw(lines):
    """Send plain text lines to Firehose (HEC Raw endpoint)."""
    batches = [lines[i:i + MAX_RECORDS] for i in range(0, len(lines), MAX_RECORDS)]
    for batch in batches:
        firehose.put_record_batch(
            DeliveryStreamName=FIREHOSE_STREAM,
            Records=[
                {"Data": (sanitize_vpcflow_line(line) + "\n").encode('utf-8')}
                for line in batch
            ]
        )
def lambda_handler(event, context):
    all_lines = []
    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        logger.info(f"Processing s3://{bucket}/{key}")
        text = read_s3_object(bucket, key)
        lines = [line for line in text.splitlines() if line.strip() and not line.startswith('#')]
        all_lines.extend(lines)
    if all_lines:
        put_records_raw(all_lines)
        logger.info(f"Sent {len(all_lines)} flow log lines to Firehose stream '{FIREHOSE_STREAM}'")
    else:
        logger.warning("No valid log lines found.")
    return {"statusCode": 200, "body": f"Processed {len(all_lines)} log lines."}
