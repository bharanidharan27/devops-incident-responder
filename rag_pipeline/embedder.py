import hashlib
import math
import re


def _embed(text: str, dimensions: int = 384) -> list[float]:
    vector = [0.0] * dimensions
    for token in re.findall(r"[a-zA-Z0-9_./:-]+", text.lower()):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[bucket] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def embed_chunks(chunks: list[str]) -> tuple[list[list[float]], list[str]]:
    return [_embed(chunk) for chunk in chunks], chunks
