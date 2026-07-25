"""
semantic_grep: a jina-grep reproduction using Gemini embeddings.

In-process semantic search over text files or in-memory strings.
Routes through Cloudflare AI Gateway (proxy.env) when available.

Model: gemini-embedding-2 (GA 2026-04-22; general-purpose AND multimodal, MRL
       truncation supported). Supersedes gemini-embedding-001, which is text-only.
       Verified 2026-07-21 through the CF gateway: text, image (image/png) and
       audio (audio/wav) all embed to the same space at the requested dim,
       L2-normalized. 001 rejects non-text with HTTP 400.
Task types used: RETRIEVAL_QUERY (query) + RETRIEVAL_DOCUMENT (corpus) — asymmetric.

Design notes:
- Serverless-mode equivalent: every call re-embeds the corpus. No persistent index.
- Caller-facing API returns structured dicts. Grep-format is a formatter, not the core.
- Flag surface mirrors jina-grep where it makes sense for a Python API (top_k, threshold,
  granularity, include). -r recursion is implicit when path is a directory.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

import numpy as np
import requests


# ---------------------------------------------------------------------------
# Credentials (reuse invoking-gemini's proxy pattern)
# ---------------------------------------------------------------------------

_CF_GATEWAY_BASE = "https://gateway.ai.cloudflare.com/v1"
_DIRECT_BASE = "https://generativelanguage.googleapis.com/v1beta"
_DEFAULT_MODEL = "gemini-embedding-2"

# Retired 2026-07-21. gemini-embedding-001 is text-only and superseded by
# gemini-embedding-2 (general-purpose AND multimodal, same request shape and
# dims). Still callable if explicitly requested, but warns — nothing in this
# skill persists vectors, so there is no index to migrate.
_RETIRED_MODELS = {
    "gemini-embedding-001": "gemini-embedding-2",
}


def _check_retired(model: str) -> None:
    """Warn once if a caller explicitly asks for a retired embedding model."""
    if model in _RETIRED_MODELS:
        import warnings
        warnings.warn(
            f"{model} is retired; use {_RETIRED_MODELS[model]} "
            f"(general-purpose and multimodal, same dims). Vectors from "
            f"different encoders are not comparable — do not mix them.",
            DeprecationWarning, stacklevel=3,
        )
_MAX_INPUT_TOKENS = 2048  # conservative; documented for embedding-001, unverified for -2
# Conservative char-per-token ratio. English prose is ~4 chars/token,
# but CJK is closer to 1 char/token and emoji can be <1. Picking 1.5 as a safe
# lower bound means we under-fill for English (some wasted context) in exchange
# for not silently overflowing the API limit for multi-script text.
_APPROX_CHARS_PER_TOKEN = 1.5


def _load_env(path: Path) -> dict:
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip("'\"")
    return out


def _embed_url(model: str, *, batch: bool = False) -> tuple[str, dict]:
    """Return (url, extra_headers) for embedContent / batchEmbedContents call."""
    endpoint = "batchEmbedContents" if batch else "embedContent"
    proxy = _load_env(Path("/mnt/project/proxy.env"))
    cf_account = proxy.get("CF_ACCOUNT_ID") or os.environ.get("CF_ACCOUNT_ID")
    cf_gateway = proxy.get("CF_GATEWAY_ID") or os.environ.get("CF_GATEWAY_ID")
    cf_token = proxy.get("CF_API_TOKEN") or os.environ.get("CF_API_TOKEN")
    if cf_account and cf_gateway and cf_token:
        url = (
            f"{_CF_GATEWAY_BASE}/{cf_account}/{cf_gateway}"
            f"/google-ai-studio/v1beta/models/{model}:{endpoint}"
        )
        headers = {"cf-aig-authorization": f"Bearer {cf_token}"}
        return url, headers
    key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("No credentials: missing proxy.env / CF_* env vars / GOOGLE_API_KEY")
    url = f"{_DIRECT_BASE}/models/{model}:{endpoint}"
    return url, {"x-goog-api-key": key}


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

TaskType = Literal[
    "RETRIEVAL_QUERY", "RETRIEVAL_DOCUMENT", "SEMANTIC_SIMILARITY",
    "CLASSIFICATION", "CLUSTERING", "QUESTION_ANSWERING", "FACT_VERIFICATION",
    "CODE_RETRIEVAL_QUERY",
]


def _embed_one(text: str, task_type: TaskType, *, model: str, dim: int,
               timeout: float = 30.0, retries: int = 2) -> np.ndarray:
    """Embed a single string. Normalizes output if dim < 3072."""
    _check_retired(model)
    url, headers = _embed_url(model)
    headers = {**headers, "Content-Type": "application/json"}
    body = {
        "content": {"parts": [{"text": text}]},
        "taskType": task_type,
        "outputDimensionality": dim,
    }
    last_err = None
    for attempt in range(retries + 1):
        try:
            r = requests.post(url, headers=headers, json=body, timeout=timeout)
            if r.status_code == 200:
                data = r.json()
                vals = data["embedding"]["values"]
                arr = np.asarray(vals, dtype=np.float32)
                if dim < 3072:
                    n = np.linalg.norm(arr)
                    if n > 0:
                        arr = arr / n
                return arr
            # Retry on 429/5xx
            if r.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(1.5 ** attempt)
                continue
            raise RuntimeError(f"Embed failed {r.status_code}: {r.text[:300]}")
        except requests.exceptions.RequestException as e:
            last_err = e
            if attempt < retries:
                time.sleep(1.5 ** attempt)
                continue
            raise
    raise RuntimeError(f"Embed failed after retries: {last_err}")


def _truncate_to_token_budget(text: str) -> str:
    """Approximate 2048-token cap by char count. Gemini will reject overflow otherwise.

    Uses a conservative chars-per-token ratio (1.5) so mixed-script / CJK text
    is not silently truncated-too-long.
    """
    limit = int(_MAX_INPUT_TOKENS * _APPROX_CHARS_PER_TOKEN)  # ~3K chars
    return text[:limit] if len(text) > limit else text


def embed_batch(texts: list[str], task_type: TaskType, *,
                model: str = _DEFAULT_MODEL, dim: int = 768,
                group_size: int = 100, timeout: float = 90.0,
                retries: int = 3) -> np.ndarray:
    """Embed N strings via :batchEmbedContents (single HTTP call per group of `group_size`).

    Returns (N, dim) array. Normalizes output rows when dim < 3072.
    """
    if not texts:
        return np.zeros((0, dim), dtype=np.float32)

    url, base_headers = _embed_url(model, batch=True)
    headers = {**base_headers, "Content-Type": "application/json"}
    out = np.zeros((len(texts), dim), dtype=np.float32)

    for start in range(0, len(texts), group_size):
        group = texts[start:start + group_size]
        body = {
            "requests": [
                {
                    "model": f"models/{model}",
                    "content": {"parts": [{"text": _truncate_to_token_budget(t)}]},
                    "taskType": task_type,
                    "outputDimensionality": dim,
                }
                for t in group
            ]
        }

        for attempt in range(retries + 1):
            try:
                r = requests.post(url, headers=headers, json=body, timeout=timeout)
                if r.status_code == 200:
                    data = r.json()
                    embs = data.get("embeddings", [])
                    if len(embs) != len(group):
                        raise RuntimeError(
                            f"Batch size mismatch: sent {len(group)}, got {len(embs)}"
                        )
                    for i, e in enumerate(embs):
                        arr = np.asarray(e["values"], dtype=np.float32)
                        if dim < 3072:
                            n = np.linalg.norm(arr)
                            if n > 0:
                                arr = arr / n
                        out[start + i] = arr
                    break  # success, next group
                if r.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                    time.sleep(1.5 ** attempt)
                    continue
                raise RuntimeError(f"Batch embed failed {r.status_code}: {r.text[:400]}")
            except requests.exceptions.RequestException as e:
                if attempt < retries:
                    time.sleep(1.5 ** attempt)
                    continue
                raise RuntimeError(f"Batch embed network error: {e}") from e

    return out


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

Granularity = Literal["line", "paragraph"]


@dataclass
class Chunk:
    path: str       # source identifier (filepath or logical id)
    line: int       # 1-indexed starting line
    text: str


def chunk_text(text: str, *, path: str = "<stdin>",
               granularity: Granularity = "paragraph") -> list[Chunk]:
    """Split text into chunks with source line numbers preserved."""
    chunks: list[Chunk] = []
    if granularity == "line":
        for i, line in enumerate(text.splitlines(), start=1):
            s = line.strip()
            if s:
                chunks.append(Chunk(path=path, line=i, text=s))
        return chunks

    # paragraph: split on blank lines, track the starting line of each paragraph
    cur_lines: list[str] = []
    cur_start: int | None = None
    for i, line in enumerate(text.splitlines(), start=1):
        if line.strip() == "":
            if cur_lines:
                chunks.append(Chunk(path=path, line=cur_start,
                                    text="\n".join(cur_lines).strip()))
                cur_lines = []
                cur_start = None
        else:
            if cur_start is None:
                cur_start = i
            cur_lines.append(line)
    if cur_lines:
        chunks.append(Chunk(path=path, line=cur_start or 1,
                            text="\n".join(cur_lines).strip()))
    return chunks


def load_corpus(path: str | Path, *, include: str = "*.txt",
                granularity: Granularity = "paragraph") -> list[Chunk]:
    """Load and chunk a file, or recursively a directory matching `include`."""
    p = Path(path)
    chunks: list[Chunk] = []
    if p.is_file():
        chunks.extend(chunk_text(p.read_text(errors="replace"),
                                 path=str(p), granularity=granularity))
        return chunks
    if p.is_dir():
        for fp in sorted(p.rglob("*")):
            if fp.is_file() and fnmatch.fnmatch(fp.name, include):
                chunks.extend(chunk_text(fp.read_text(errors="replace"),
                                         path=str(fp), granularity=granularity))
        return chunks
    raise FileNotFoundError(path)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

@dataclass
class Match:
    path: str
    line: int
    text: str
    score: float


def semantic_grep(query: str, corpus: str | Path | list[Chunk], *,
                  top_k: int = 10, threshold: float | None = None,
                  granularity: Granularity = "paragraph",
                  include: str = "*.txt",
                  model: str = _DEFAULT_MODEL, dim: int = 768,
                  task: Literal["text", "code"] = "text") -> list[Match]:
    """Semantic search over a file, directory, or pre-chunked list.

    - top_k: max results (set to None for all above threshold)
    - threshold: cosine similarity cutoff (None = no filter, use top_k only)
    - granularity: paragraph (default) or line
    - task: 'text' → RETRIEVAL_QUERY/DOCUMENT; 'code' → CODE_RETRIEVAL_QUERY/DOCUMENT

    Raises ValueError on empty query. Returns [] for empty corpus without
    hitting the API.
    """
    if not query or not query.strip():
        raise ValueError("query must be non-empty")

    # Resolve corpus
    if isinstance(corpus, list):
        chunks = corpus
    else:
        chunks = load_corpus(corpus, include=include, granularity=granularity)
    if not chunks:
        return []

    q_task: TaskType = "CODE_RETRIEVAL_QUERY" if task == "code" else "RETRIEVAL_QUERY"
    d_task: TaskType = "RETRIEVAL_DOCUMENT"

    q_vec = _embed_one(_truncate_to_token_budget(query), q_task, model=model, dim=dim)
    d_vecs = embed_batch([c.text for c in chunks], d_task, model=model, dim=dim)

    # Cosine sim — vectors are normalized when dim < 3072 (handled in _embed_one)
    scores = d_vecs @ q_vec  # (N,)

    # Rank
    order = np.argsort(-scores)
    matches: list[Match] = []
    for idx in order:
        s = float(scores[idx])
        if threshold is not None and s < threshold:
            break
        matches.append(Match(path=chunks[idx].path, line=chunks[idx].line,
                             text=chunks[idx].text, score=s))
        if top_k is not None and len(matches) >= top_k:
            break
    return matches


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def format_grep(matches: list[Match], *, max_text_chars: int = 200,
                show_score: bool = True) -> str:
    """Format matches in grep-compatible `path:line: text` form."""
    lines = []
    for m in matches:
        snippet = m.text.replace("\n", " ")
        if len(snippet) > max_text_chars:
            snippet = snippet[:max_text_chars - 1] + "…"
        prefix = f"{m.path}:{m.line}:"
        tail = f"  [{m.score:.3f}]" if show_score else ""
        lines.append(f"{prefix} {snippet}{tail}")
    return "\n".join(lines)
