"""S3 presigned URL generation for audio streaming."""

import json
import logging
import os

import boto3
from botocore.config import Config

logger = logging.getLogger("leerio.storage")

_client = None


def _get_client():
    global _client
    if _client is None:
        endpoint = os.environ.get("S3_ENDPOINT", "")
        access_key = os.environ.get("S3_ACCESS_KEY", "")
        secret_key = os.environ.get("S3_SECRET_KEY", "")
        if not all([endpoint, access_key, secret_key]):
            logger.warning("S3 not configured — audio streaming will fail")
            return None
        _client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(
                signature_version="s3v4",
                connect_timeout=10,
                read_timeout=30,
            ),
        )
    return _client


def get_s3_object(s3_key: str, range_header: str | None = None):
    """Get an S3 object (or range) for streaming. Returns (body, content_type, content_length, status, content_range) or None."""
    client = _get_client()
    if not client:
        return None
    bucket = os.environ.get("S3_BUCKET", "leerio-books")
    try:
        kwargs = {"Bucket": bucket, "Key": s3_key}
        if range_header:
            kwargs["Range"] = range_header
        resp = client.get_object(**kwargs)
        return {
            "body": resp["Body"],
            "content_type": resp.get("ContentType", "audio/mpeg"),
            "content_length": resp.get("ContentLength", 0),
            "status": resp.get("ResponseMetadata", {}).get("HTTPStatusCode", 200),
            "content_range": resp.get("ContentRange"),
        }
    except Exception as e:
        logger.error("S3 get_object failed for %s: %s", s3_key, e)
        return None


def s3_object_exists(s3_key: str) -> bool:
    """Check if an object exists in S3 via HEAD request."""
    client = _get_client()
    if not client:
        return False
    bucket = os.environ.get("S3_BUCKET", "leerio-books")
    try:
        client.head_object(Bucket=bucket, Key=s3_key)
        return True
    except Exception:
        return False


def get_presigned_url(s3_key: str, expires: int = 3600) -> str | None:
    client = _get_client()
    if not client:
        return None
    bucket = os.environ.get("S3_BUCKET", "leerio-books")
    try:
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": s3_key},
            ExpiresIn=expires,
        )
    except Exception:
        return None


def upload_file_to_s3(local_path: str, s3_key: str) -> None:
    """Upload a local file to S3."""
    client = _get_client()
    if not client:
        raise RuntimeError("S3 not configured")
    bucket = os.environ.get("S3_BUCKET", "leerio-books")
    client.upload_file(local_path, bucket, s3_key)


def upload_json_to_s3(data: dict | list, s3_key: str) -> None:
    """Upload a JSON object to S3."""
    client = _get_client()
    if not client:
        raise RuntimeError("S3 not configured")
    bucket = os.environ.get("S3_BUCKET", "leerio-books")
    body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    client.put_object(Bucket=bucket, Key=s3_key, Body=body, ContentType="application/json")


def delete_s3_prefix(prefix: str) -> int:
    """Delete all objects under a prefix. Returns count deleted."""
    client = _get_client()
    if not client:
        return 0
    bucket = os.environ.get("S3_BUCKET", "leerio-books")
    paginator = client.get_paginator("list_objects_v2")
    deleted = 0
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        objects = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
        if objects:
            client.delete_objects(Bucket=bucket, Delete={"Objects": objects})
            deleted += len(objects)
    return deleted
