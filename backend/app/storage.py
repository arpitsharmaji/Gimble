"""File storage behind one interface, so the same code runs on a laptop (local folder) and in production (S3-compatible bucket).

Public files  = profile photos   (served at /uploads/<name>, or from a CDN/public URL if S3_PUBLIC_BASE_URL is set)
Private files = ID-verification  (never public; only admins can read them through the API)

Database rows always store the canonical path "/uploads/<name>", so you can change backends later without touching data.
"""
import logging, re
from pathlib import Path
from .config import settings

log = logging.getLogger("gimble.storage")
NAME_RE = re.compile(r"^u(\d+)_[0-9a-f]{16}\.jpg$")        # public profile photos
PRIVATE_RE = re.compile(r"^kyc_[0-9a-f]{24}\.jpg$")          # private ID files


class LocalStorage:
    kind = "local"

    def _pub(self, name): return settings.UPLOAD_DIR / name
    def _priv(self, name): return settings.PRIVATE_DIR / name

    def put_public(self, name: str, data: bytes):
        settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True); self._pub(name).write_bytes(data)

    def get_public(self, name: str) -> bytes | None:
        p = self._pub(name); return p.read_bytes() if p.is_file() else None

    def exists_public(self, name: str) -> bool: return self._pub(name).is_file()

    def count_public(self, prefix: str) -> int:
        return len(list(settings.UPLOAD_DIR.glob(prefix + "*"))) if settings.UPLOAD_DIR.exists() else 0

    def put_private(self, name: str, data: bytes):
        settings.PRIVATE_DIR.mkdir(parents=True, exist_ok=True); self._priv(name).write_bytes(data)

    def get_private(self, name: str) -> bytes | None:
        p = self._priv(name); return p.read_bytes() if p.is_file() else None

    def delete_private(self, name: str):
        self._priv(name).unlink(missing_ok=True)

    def ping(self) -> str: return f"local:{settings.UPLOAD_DIR}"


class S3Storage:
    kind = "s3"

    def __init__(self):
        import boto3
        from botocore.config import Config
        self.c = boto3.client("s3", endpoint_url=settings.S3_ENDPOINT_URL or None, region_name=settings.S3_REGION,
                              aws_access_key_id=settings.S3_ACCESS_KEY_ID, aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
                              config=Config(retries={"max_attempts": 3, "mode": "standard"}, signature_version="s3v4"))
        self.pub = settings.S3_PUBLIC_BUCKET
        self.priv = settings.S3_PRIVATE_BUCKET or settings.S3_PUBLIC_BUCKET   # same bucket => keys are prefixed "private/"
        self.priv_prefix = "" if settings.S3_PRIVATE_BUCKET else "private/"   # dev/test convenience only (see config validation)
        self.pub_prefix = ""

    def _get(self, bucket, key):
        try:
            return self.c.get_object(Bucket=bucket, Key=key)["Body"].read()
        except self.c.exceptions.NoSuchKey:
            return None
        except Exception as e:  # 404 style errors differ between providers
            if "404" in str(e) or "NoSuchKey" in str(e) or "Not Found" in str(e): return None
            raise

    def put_public(self, name, data):
        self.c.put_object(Bucket=self.pub, Key=self.pub_prefix + name, Body=data, ContentType="image/jpeg", CacheControl="public, max-age=31536000, immutable")

    def get_public(self, name): return self._get(self.pub, self.pub_prefix + name)

    def exists_public(self, name):
        try: self.c.head_object(Bucket=self.pub, Key=self.pub_prefix + name); return True
        except Exception: return False

    def count_public(self, prefix):
        r = self.c.list_objects_v2(Bucket=self.pub, Prefix=self.pub_prefix + prefix, MaxKeys=100)
        return r.get("KeyCount", 0)

    def put_private(self, name, data):
        self.c.put_object(Bucket=self.priv, Key=self.priv_prefix + name, Body=data, ContentType="image/jpeg")

    def get_private(self, name): return self._get(self.priv, self.priv_prefix + name)

    def delete_private(self, name):
        self.c.delete_object(Bucket=self.priv, Key=self.priv_prefix + name)

    def ping(self) -> str:
        self.c.head_bucket(Bucket=self.pub); return f"s3:{self.pub}"


_storage = None


def get_storage():
    global _storage
    if _storage is None:
        _storage = S3Storage() if settings.STORAGE_BACKEND == "s3" else LocalStorage()
    return _storage


def reset_storage():
    """Tests / config changes: rebuild the backend on next use."""
    global _storage
    _storage = None


def media_url(path: str) -> str:
    """Canonical '/uploads/<name>' -> URL the browser should load (CDN/public bucket URL if configured)."""
    if not path or not path.startswith("/uploads/"): return path
    if settings.STORAGE_BACKEND == "s3" and settings.S3_PUBLIC_BASE_URL:
        return f"{settings.S3_PUBLIC_BASE_URL}/{path.rsplit('/', 1)[1]}"
    return path


def canonical_photo(url: str, user_id: int) -> str | None:
    """Accept '/uploads/x.jpg' or the CDN form of it; return canonical path if it is this user's real photo, else None."""
    name = url.rsplit("/", 1)[-1]
    m = NAME_RE.match(name)
    if not m or int(m.group(1)) != user_id or not get_storage().exists_public(name):
        return None
    return f"/uploads/{name}"
