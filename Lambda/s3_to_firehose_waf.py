import os
import io
import re
import gzip
import logging
from urllib.parse import unquote_plus
import boto3
from botocore.exceptions import ClientError
# --- AWS clients ---
s3 = boto3.client('s3')
firehose = boto3.client('firehose')
# --- Environment vars ---
FIREHOSE_STREAM = os.environ['FIREHOSE_STREAM']             # required
MAX_RECORDS = int(os.environ.get('MAX_RECORDS', '450'))     # optional (≤ 500)
# --- Logging ---
logger = logging.getLogger()
logger.setLevel(logging.INFO)
# Match a leading ISO-8601 timestamp like "2025-09-13T21:32:51Z " or "2025-09-13T21:32:51.660Z "
# Allow 1–9 fractional digits and ANY horizontal whitespace afterwards.
ISO_PREFIX = re.compile(
    r'^\s*\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z[\t ]+'
)
def _iter_lines_from_streaming_text_body(body):
    buf = io.StringIO()
    for chunk in iter(lambda: body.read(1024 * 1024), b''):
        buf.write(chunk.decode('utf-8', errors='replace'))
        buf.seek(0)
        for line in buf.read().splitlines(True):
            if line.endswith('\n'):
                yield line[:-1]
            else:
                buf = io.StringIO(line)
                break
        else:
            buf = io.StringIO()
    rem = buf.getvalue()
    if rem:
        yield rem
def _iter_lines_from_streaming_gzip_body(body):
    with gzip.GzipFile(fileobj=body) as gz:
        reader = io.BufferedReader(gz)
        text_buf = io.StringIO()
        while True:
            chunk = reader.read(1024 * 1024)
            if not chunk:
                break
            text_buf.write(chunk.decode('utf-8', errors='replace'))
            text_buf.seek(0)
            for line in text_buf.read().splitlines(True):
                if line.endswith('\n'):
                    yield line[:-1]
                else:
                    text_buf = io.StringIO(line)
                    break
            else:
                text_buf = io.StringIO()
        rem = text_buf.getvalue()
        if rem:
            yield rem
def iter_s3_lines(bucket: str, key: str):
    obj = s3.get_object(Bucket=bucket, Key=key)
    body = obj['Body']
    if key.endswith('.gz'):
        yield from _iter_lines_from_streaming_gzip_body(body)
    else:
        yield from _iter_lines_from_streaming_text_body(body)
def strip_to_json(line: str) -> str:
    """
    Remove a leading ISO-8601 prefix if present.
    As a safety net, if anything precedes the first '{', drop it.
    """
    # Try ISO removal first
    stripped = ISO_PREFIX.sub('', line)
    if stripped and stripped[0] == '{':
        return stripped
    # Fallback: trim up to the first '{' if it exists
    brace = stripped.find('{')
    return stripped[brace:] if brace != -1 else ''  # '' means "not JSON"
def to_firehose_record(line: str) -> dict:
    if not line.endswith('\n'):
        line += '\n'
    return {"Data": line.encode('utf-8', errors='replace')}
def put_records_with_retries(stream_name: str, records: list, max_attempts: int = 3):
    remaining = records
    for attempt in range(1, max_attempts + 1):
        if not remaining:
            return 0
        resp = firehose.put_record_batch(DeliveryStreamName=stream_name, Records=remaining)
        failed = resp.get("FailedPutCount", 0)
        if failed == 0:
            return 0
        retry = []
        for rec, rr in zip(remaining, resp.get("RequestResponses", [])):
            if "ErrorCode" in rr:
                retry.append(rec)
        logger.warning(f"Firehose batch had {failed} failures; retrying {len(retry)} "
                       f"(attempt {attempt}/{max_attempts})")
        remaining = retry
    return len(remaining)  # still failed after retries
def lambda_handler(event, context):
    total_lines = 0
    stripped_to_json = 0
    skipped_nonjson = 0
    sent = 0
    failed_after_retry = 0
    batch = []
    def flush_batch():
        nonlocal batch, sent, failed_after_retry
        if not batch:
            return
        failed = put_records_with_retries(FIREHOSE_STREAM, batch)
        sent += (len(batch) - failed)
        failed_after_retry += failed
        batch = []
    for rec in event.get('Records', []):
        bucket = rec['s3']['bucket']['name']
        raw_key = rec['s3']['object']['key']
        key = unquote_plus(raw_key)
        logger.info(f"Processing WAF logs from s3://{bucket}/{key} (raw key: {raw_key})")
        try:
            for line in iter_s3_lines(bucket, key):
                total_lines += 1
                cleaned = strip_to_json(line)
                if not cleaned or cleaned[0] != '{':
                    skipped_nonjson += 1
                    continue
                stripped_to_json += 1
                batch.append(to_firehose_record(cleaned))
                if len(batch) >= MAX_RECORDS:
                    flush_batch()
        except ClientError as e:
            logger.error(f"S3 get/read failed for s3://{bucket}/{key}: {e}")
    flush_batch()
    logger.info(
        f"WAF Lambda summary: total_lines={total_lines}, "
        f"json_ready={stripped_to_json}, skipped_nonjson={skipped_nonjson}, "
        f"sent={sent}, firehose_failed_after_retry={failed_after_retry}, "
        f"stream='{FIREHOSE_STREAM}'."
    )
    return {
        "statusCode": 200,
        "body": (f"Processed {total_lines} lines; forwarded {sent} JSON records "
                 f"to Firehose '{FIREHOSE_STREAM}'. Skipped {skipped_nonjson}.")
    }
