"""Validação antes de tocar no banco: camada, CRS (SIRGAS 2000) e contagem."""

import re
from pathlib import Path

import pyogrio

# Feições na malha nacional: 5.572 até 2022, 5.573 em 2025 (inclui as duas áreas operacionais)
FEICOES_MUNICIPIOS = (5_560, 5_580)


class ValidacaoError(ValueError):
    pass


def camada_municipios(camadas: list[str]) -> str:
    """Escolhe a camada de municípios: a única, ou a que parece de municípios (BR_Municipios_2025, BRMUE250GC_SIR)."""
    if len(camadas) == 1:
        return camadas[0]
    candidatas = [c for c in camadas if re.search(r"munic|MUE\d", c, re.IGNORECASE)]
    if len(candidatas) != 1:
        raise ValidacaoError(f"camada de municípios ambígua: {camadas}")
    return candidatas[0]


def crs_sirgas2000(crs: str | None) -> bool:
    return bool(crs) and ("4674" in crs or "SIRGAS 2000" in crs.upper() or "SIRGAS_2000" in crs.upper())


def validar_zip(zip_path: Path, feicoes: tuple[int, int] = FEICOES_MUNICIPIOS) -> dict:
    fonte = f"/vsizip/{Path(zip_path).resolve()}"
    camada = camada_municipios([nome for nome, _ in pyogrio.list_layers(fonte)])
    info = pyogrio.read_info(fonte, layer=camada)
    if not crs_sirgas2000(info["crs"]):
        raise ValidacaoError(f"CRS inesperado em {camada}: {info['crs']}")
    n = int(info["features"])
    if not feicoes[0] <= n <= feicoes[1]:
        raise ValidacaoError(f"{n} feições em {camada}, esperado entre {feicoes[0]} e {feicoes[1]}")
    return {"camada": camada, "feicoes": n, "crs": info["crs"], "colunas": list(info["fields"])}
