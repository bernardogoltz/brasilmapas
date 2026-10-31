"""Malhas intramunicipais do Censo 2022: setores, bairros, distritos e subdistritos (dado estático)."""

from ibge.geoftp import GEOFTP

BASE = f"{GEOFTP}/malhas_de_setores_censitarios__divisoes_intramunicipais/censo_2022"
EDICAO = 2022

# Feições conferidas no geoftp em 30/10/2026 (SHP nacional, uma feição por código)
FEICOES = {
    "setores": 468_099,
    "bairros": 17_575,
    "distritos": 10_699,
    "subdistritos": 11_307,
}
CAMADAS = list(FEICOES)


def url(camada: str) -> str:
    return f"{BASE}/{camada}/shp/BR/BR_{camada}_CD2022.zip"


def tabela(camada: str) -> str:
    return f"raw.censo2022_{camada}"


def faixa(camada: str, folga: float = 0.01) -> tuple[int, int]:
    """Contagem esperada ± 1%: o IBGE republica correções sem mudar o nome do arquivo."""
    n = FEICOES[camada]
    return int(n * (1 - folga)), int(n * (1 + folga))
