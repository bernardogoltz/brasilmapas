"""API Localidades do IBGE → raw.localidades_<nivel> (uma linha JSONB por item)."""

import gzip
import json
import urllib.request

API = "https://servicodados.ibge.gov.br/api/v1/localidades"
NIVEIS = ["estados", "municipios", "distritos", "subdistritos", "regioes-imediatas", "regioes-intermediarias"]


def url(nivel: str) -> str:
    return f"{API}/{nivel}?view=nivelado"


def tabela(nivel: str) -> str:
    return "raw.localidades_" + nivel.replace("-", "_")


def buscar(nivel: str, timeout: int = 120) -> list[dict]:
    with urllib.request.urlopen(url(nivel), timeout=timeout) as r:
        itens = decodificar(r.read())
    if not isinstance(itens, list) or not itens:
        raise ValueError(f"resposta vazia ou inesperada para {nivel}")
    return itens


def decodificar(corpo: bytes):
    """JSON da API, que às vezes vem em gzip mesmo sem Accept-Encoding."""
    if corpo[:2] == b"\x1f\x8b":
        corpo = gzip.decompress(corpo)
    return json.loads(corpo)


def ddl(nivel: str) -> str:
    return (
        f"CREATE TABLE IF NOT EXISTS {tabela(nivel)} ("
        "coletado_em date NOT NULL, dados jsonb NOT NULL)"
    )


def linhas(itens: list[dict]) -> list[tuple[str]]:
    return [(json.dumps(i, ensure_ascii=False),) for i in itens]
