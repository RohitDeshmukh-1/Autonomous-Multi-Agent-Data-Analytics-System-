"""
storage/supabase_storage.py
Upload/download user files (CSV, SQLite) via Supabase Storage.
"""

import os
import uuid

import requests
from supabase import Client, create_client


def get_supabase() -> Client:
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"],
    )


def upload_file(
    file_bytes: bytes,
    filename: str,
    bucket: str = "user-uploads",
    content_type: str = "text/csv",
) -> str:
    """
    Upload bytes to Supabase Storage.
    Returns the public URL of the uploaded file.
    """
    key = f"{uuid.uuid4()}/{filename}"
    sb = get_supabase()
    sb.storage.from_(bucket).upload(
        key,
        file_bytes,
        file_options={"content-type": content_type},
    )
    return sb.storage.from_(bucket).get_public_url(key)


def download_file(public_url: str) -> bytes:
    """Download a file from its Supabase public URL."""
    resp = requests.get(public_url, timeout=30)
    resp.raise_for_status()
    return resp.content


def delete_file(public_url: str, bucket: str = "user-uploads") -> None:
    """Delete a file from Supabase Storage by its public URL."""
    # Extract the key from the URL
    # URL format: https://<ref>.supabase.co/storage/v1/object/public/<bucket>/<key>
    parts = public_url.split(f"/object/public/{bucket}/")
    if len(parts) != 2:
        raise ValueError(f"Cannot parse Supabase URL: {public_url}")
    key = parts[1]
    sb = get_supabase()
    sb.storage.from_(bucket).remove([key])
