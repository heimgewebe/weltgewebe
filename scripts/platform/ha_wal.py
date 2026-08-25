from __future__ import annotations

import hashlib
import hmac
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

import kind_reference as ref
from ha_common import sha256_text

S3_BUCKET = "weltgewebe-postgres"

def wal_segment_position(name: str) -> tuple[int, int, int]:
    normalized = name.strip().upper()
    if len(normalized) != 24 or any(character not in "0123456789ABCDEF" for character in normalized):
        raise ref.ProofError(f"invalid PostgreSQL WAL segment name: {name!r}")
    return tuple(int(normalized[offset : offset + 8], 16) for offset in (0, 8, 16))

def wal_archived_at_or_after(observed: str, required: str) -> bool:
    return wal_segment_position(observed) >= wal_segment_position(required)

def _aws_sigv4_signing_key(secret: str, date_stamp: str) -> bytes:
    date_key = hmac.new(
        ("AWS4" + secret).encode("utf-8"), date_stamp.encode("utf-8"), hashlib.sha256
    ).digest()
    region_key = hmac.new(date_key, b"us-east-1", hashlib.sha256).digest()
    service_key = hmac.new(region_key, b"s3", hashlib.sha256).digest()
    return hmac.new(service_key, b"aws4_request", hashlib.sha256).digest()

def _aws_canonical_query(parameters: dict[str, str]) -> str:
    quote = lambda value: urllib.parse.quote(str(value), safe="-_.~")
    return "&".join(
        f"{quote(key)}={quote(value)}" for key, value in sorted(parameters.items())
    )

def s3_list_object_keys(
    address: str,
    s3_access_key: str,
    s3_secret_key: str,
    *,
    prefix: str = "",
) -> list[str]:
    host = f"{address}:8333"
    continuation: str | None = None
    keys: list[str] = []
    for _page in range(20):
        parameters = {"list-type": "2", "prefix": prefix}
        if continuation:
            parameters["continuation-token"] = continuation
        query = _aws_canonical_query(parameters)
        now = datetime.now(timezone.utc)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        payload_hash = hashlib.sha256(b"").hexdigest()
        canonical_uri = "/" + urllib.parse.quote(S3_BUCKET, safe="-_.~")
        canonical_headers = (
            f"host:{host}\n"
            f"x-amz-content-sha256:{payload_hash}\n"
            f"x-amz-date:{amz_date}\n"
        )
        signed_headers = "host;x-amz-content-sha256;x-amz-date"
        canonical_request = "\n".join(
            [
                "GET",
                canonical_uri,
                query,
                canonical_headers,
                signed_headers,
                payload_hash,
            ]
        )
        scope = f"{date_stamp}/us-east-1/s3/aws4_request"
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                amz_date,
                scope,
                hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
            ]
        )
        signature = hmac.new(
            _aws_sigv4_signing_key(s3_secret_key, date_stamp),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        authorization = (
            "AWS4-HMAC-SHA256 "
            f"Credential={s3_access_key}/{scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )
        request = urllib.request.Request(
            f"http://{host}{canonical_uri}?{query}",
            headers={
                "Authorization": authorization,
                "x-amz-content-sha256": payload_hash,
                "x-amz-date": amz_date,
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = response.read()
        except (OSError, urllib.error.URLError) as error:
            raise ref.ProofError(
                f"read-only S3 object listing failed for proof store {host}"
            ) from error
        try:
            root = ET.fromstring(payload)
        except ET.ParseError as error:
            raise ref.ProofError("proof object-store S3 listing returned invalid XML") from error
        keys.extend(
            element.text
            for element in root.findall(".//{*}Key")
            if isinstance(element.text, str) and element.text
        )
        truncated = root.find(".//{*}IsTruncated")
        if truncated is None or str(truncated.text).lower() != "true":
            return keys
        token = root.find(".//{*}NextContinuationToken")
        if token is None or not token.text:
            raise ref.ProofError("truncated S3 listing has no continuation token")
        continuation = token.text
    raise ref.ProofError("proof object-store S3 listing exceeded 20 pages")

def wal_object_key_matches(key: str, server_name: str, wal_segment: str) -> bool:
    wal_segment_position(wal_segment)
    parts = [part for part in key.split("/") if part]
    if len(parts) < 3 or parts[0] != server_name or parts[1] != "wals":
        return False
    basename = parts[-1]
    return basename in {wal_segment, f"{wal_segment}.gz"}

def require_wal_object_identity(
    keys: list[str], server_name: str, wal_segment: str
) -> dict[str, Any]:
    matches = sorted(
        key
        for key in set(keys)
        if wal_object_key_matches(key, server_name, wal_segment)
    )
    if len(matches) != 1:
        raise ref.ProofError(
            "forced WAL segment is not uniquely present in proof object store: "
            f"server={server_name} wal={wal_segment} matches={len(matches)}"
        )
    key = matches[0]
    return {
        "server_name": server_name,
        "wal_segment": wal_segment,
        "object_key": key,
        "object_key_sha256": sha256_text(key),
    }

def object_store_wal_evidence(
    address: str,
    s3_access_key: str,
    s3_secret_key: str,
    *,
    server_name: str,
    wal_segment: str,
) -> dict[str, Any]:
    keys = s3_list_object_keys(
        address, s3_access_key, s3_secret_key, prefix=f"{server_name}/"
    )
    identity = require_wal_object_identity(keys, server_name, wal_segment)
    return {
        **identity,
        "bucket": S3_BUCKET,
        "listed_key_count": len(keys),
        "probe": "signed-s3-list-objects-v2-read-only",
        "read_only": True,
        "archive_command_reused_as_probe": False,
    }
