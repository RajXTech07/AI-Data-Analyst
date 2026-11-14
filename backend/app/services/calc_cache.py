import hashlib
import json
from typing import Any
import uuid

class CalcCache:
    """
    High-performance in-memory and database query result cache.
    Keyed by (dataset_id, data_version, tool_name, parameters_hash).
    """

    def __init__(self):
        self._cache: dict[str, Any] = {}

    def _make_key(self, dataset_id: uuid.UUID | str, data_version: str, tool_name: str, params: dict[str, Any] | None) -> str:
        param_str = json.dumps(params or {}, sort_keys=True, default=str)
        param_hash = hashlib.sha256(param_str.encode("utf-8")).hexdigest()[:16]
        return f"{str(dataset_id)}:{data_version}:{tool_name}:{param_hash}"

    def get(self, dataset_id: uuid.UUID | str, data_version: str, tool_name: str, params: dict[str, Any] | None) -> Any | None:
        key = self._make_key(dataset_id, data_version, tool_name, params)
        return self._cache.get(key)

    def set(self, dataset_id: uuid.UUID | str, data_version: str, tool_name: str, params: dict[str, Any] | None, value: Any) -> None:
        key = self._make_key(dataset_id, data_version, tool_name, params)
        self._cache[key] = value

    def invalidate(self, dataset_id: uuid.UUID | str) -> int:
        """Invalidates all cached computations for a given dataset."""
        ds_prefix = f"{str(dataset_id)}:"
        keys_to_remove = [k for k in self._cache if k.startswith(ds_prefix)]
        for k in keys_to_remove:
            del self._cache[k]
        return len(keys_to_remove)

calc_cache = CalcCache()
