import hashlib
from pathlib import Path
import uuid
from app.core.config import settings
from app.core.errors import FileTooLarge

class LocalStorage:
    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or settings.resolved_storage_path
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_file(self, content: bytes, extension: str = "csv") -> tuple[str, str, int]:
        """
        Saves bytes to disk.
        Returns: (storage_path, sha256_hash, size_bytes)
        """
        size_bytes = len(content)
        if size_bytes > settings.max_upload_bytes:
            raise FileTooLarge(f"File size ({size_bytes} bytes) exceeds limit of {settings.MAX_UPLOAD_MB} MB")

        sha256 = hashlib.sha256(content).hexdigest()
        filename = f"{uuid.uuid4().hex}_{sha256[:12]}.{extension}"
        target_path = self.base_dir / filename

        with open(target_path, "wb") as f:
            f.write(content)

        return str(target_path), sha256, size_bytes

    def read_file(self, storage_path: str) -> bytes:
        p = Path(storage_path)
        if not p.is_file():
            raise FileNotFoundError(f"Storage file not found: {storage_path}")
        return p.read_bytes()

    def delete_file(self, storage_path: str) -> bool:
        p = Path(storage_path)
        if p.is_file():
            p.unlink()
            return True
        return False

storage_service = LocalStorage()
