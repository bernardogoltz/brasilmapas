"""Download com sha256, idempotente: pula se o arquivo local já tem o tamanho remoto."""

import hashlib
import os
import urllib.request
from pathlib import Path


def sha256(caminho: Path, bloco: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        while b := f.read(bloco):
            h.update(b)
    return h.hexdigest()


def tamanho_remoto(url: str, timeout: int = 60) -> int | None:
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        n = r.headers.get("Content-Length")
    return int(n) if n else None


def baixar(url: str, destino: Path, tamanho: int | None = None, timeout: int = 300) -> dict:
    """Baixa `url` para `destino` (via .part + rename). Devolve bytes, sha256 e se baixou."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists() and tamanho is not None and destino.stat().st_size == tamanho:
        return {"bytes": tamanho, "sha256": sha256(destino), "baixado": False}

    parcial = destino.with_name(destino.name + ".part")
    h = hashlib.sha256()
    with urllib.request.urlopen(url, timeout=timeout) as r, open(parcial, "wb") as f:
        while b := r.read(1 << 20):
            h.update(b)
            f.write(b)
    n = parcial.stat().st_size
    if tamanho is not None and n != tamanho:
        parcial.unlink()
        raise IOError(f"download incompleto: {n} de {tamanho} bytes ({url})")
    os.replace(parcial, destino)
    return {"bytes": n, "sha256": h.hexdigest(), "baixado": True}
