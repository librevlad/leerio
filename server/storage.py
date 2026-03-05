"""S3 presigned URL generation for audio streaming."""

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
            config=Config(signature_version="s3v4"),
        )
    return _client


def get_presigned_url(s3_key: str, expires: int = 3600) -> str | None:
    client = _get_client()
    if not client:
        return None
    bucket = os.environ.get("S3_BUCKET", "leerio-books")
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": s3_key},
        ExpiresIn=expires,
    )
