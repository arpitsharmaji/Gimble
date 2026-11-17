#!/usr/bin/env python3
"""Copy existing local profile photos into your S3/R2 bucket (one-time, safe to re-run).

    STORAGE_BACKEND=s3 S3_PUBLIC_BUCKET=... S3_PRIVATE_BUCKET=... S3_ACCESS_KEY_ID=... S3_SECRET_ACCESS_KEY=... \\
    S3_ENDPOINT_URL=... python scripts/sync_uploads_to_s3.py ./uploads

Only profile photos (u<id>_<hex>.jpg) are copied. ID-verification files are deleted after review and are not migrated.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.storage import get_storage, NAME_RE  # noqa: E402

if __name__ == "__main__":
    folder = Path(sys.argv[1] if len(sys.argv) > 1 else "uploads")
    store, n = get_storage(), 0
    if store.kind != "s3":
        sys.exit("Set STORAGE_BACKEND=s3 and the S3_* variables first.")
    for f in sorted(folder.glob("*.jpg")):
        if NAME_RE.match(f.name):
            if not store.exists_public(f.name):
                store.put_public(f.name, f.read_bytes()); n += 1
    print(f"Uploaded {n} new photo(s) from {folder}")
