import os
import json
import hashlib
from io import BytesIO
from typing import Tuple, Any, Dict

import numpy as np
import faiss


def compute_doc_id(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()[:32]


def get_cache_dir(base_dir: str, doc_id: str) -> str:
    path = os.path.join(base_dir, doc_id)
    os.makedirs(path, exist_ok=True)
    return path


def path_in_cache(cache_dir: str, name: str) -> str:
    return os.path.join(cache_dir, name)


def save_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_numpy(path: str, arr: np.ndarray) -> None:
    np.save(path, arr)


def load_numpy(path: str) -> np.ndarray:
    return np.load(path, allow_pickle=False)


def save_faiss(path: str, index: faiss.Index) -> None:
    faiss.write_index(index, path)


def load_faiss(path: str) -> faiss.Index:
    return faiss.read_index(path)


def has_cached_artifacts(cache_dir: str) -> bool:
    required = [
        path_in_cache(cache_dir, "chunks.json"),
        path_in_cache(cache_dir, "faiss.index"),
        path_in_cache(cache_dir, "topics_summaries.json"),
        path_in_cache(cache_dir, "sections.json"),
    ]
    return all(os.path.exists(p) for p in required) 