"""OCR 结果按文件 hash 缓存，避免重复跑 OCR。"""
from __future__ import annotations
import hashlib
import os
import pickle


def file_hash(path: str) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def cache_path(cache_dir: str, key: str) -> str:
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"{key}.pkl")


def load(cache_dir: str, key: str):
    p = cache_path(cache_dir, key)
    if not os.path.exists(p):
        return None
    try:
        with open(p, "rb") as f:
            return pickle.load(f)
    except Exception:
        return None


def save(cache_dir: str, key: str, obj):
    p = cache_path(cache_dir, key)
    with open(p, "wb") as f:
        pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)
