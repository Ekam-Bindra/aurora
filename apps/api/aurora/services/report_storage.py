"""Durable S3 archival for exported board packs.

When ``S3_BUCKET`` is configured (ECS injects it; local dev usually not),
every successful export is written through to
``reports/{company_id}/{report_id}/{filename}`` and a one-hour presigned URL
is returned for sharing. Archival is best-effort: any S3 failure logs a
warning and the download itself proceeds unaffected.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..core.config import get_settings
from ..core.logging import get_logger

logger = get_logger("aurora.report_storage")

_PRESIGN_TTL_SECONDS = 3600


def _s3_client():
    """Factory kept module-level so tests can monkeypatch it."""
    import boto3

    settings = get_settings()
    return boto3.client(
        "s3",
        region_name=settings.s3_region,
        endpoint_url=settings.s3_endpoint or None,
    )


def archive_export(
    report: Dict[str, Any],
    *,
    body: bytes,
    media_type: str,
    filename: str,
) -> Optional[str]:
    """Write the export to S3 and return a presigned URL, or None when
    archival is unavailable (no bucket) or fails (best-effort)."""
    settings = get_settings()
    bucket = settings.s3_bucket
    if not bucket:
        return None

    key = f"reports/{report.get('company_id')}/{report.get('id')}/{filename}"
    try:
        client = _s3_client()
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType=media_type,
        )
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=_PRESIGN_TTL_SECONDS,
        )
    except Exception as exc:
        logger.warning("Board pack archival to s3://%s/%s failed: %s", bucket, key, exc)
        return None
