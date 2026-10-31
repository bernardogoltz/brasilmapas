"""Listagem do geoftp do IBGE e descoberta das edições da malha municipal."""

import re
import urllib.request

GEOFTP = "https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais"
MALHAS = f"{GEOFTP}/malhas_municipais"

# Plano B quando a listagem falha ou muda de formato (ver README, lição 6)
MANIFESTO = {
    2015: "municipio_2015/Brasil/BR/br_municipios.zip",
    2019: "municipio_2019/Brasil/BR/br_municipios_20200807.zip",
    2022: "municipio_2022/Brasil/BR/BR_Municipios_2022.zip",
    2025: "municipio_2025/Brasil/BR_Municipios_2025.zip",
}

_HREF = re.compile(r'href="([^"?#]+)"')
_ZIP_MUNICIPIOS = re.compile(r"^br_municipios[^/]*\.zip$", re.IGNORECASE)


def ler(url: str, timeout: int = 60) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read().decode("latin-1")


def links(html: str) -> list[str]:
    """Entradas relativas de uma listagem do Apache (sem pai, ordenação nem links externos)."""
    return [h for h in _HREF.findall(html) if not h.startswith(("/", "http:", "https:"))]


def edicoes(html: str) -> list[int]:
    return sorted(int(m[1]) for h in links(html) if (m := re.fullmatch(r"municipio_(\d{4})/", h)))


def zip_municipios(html: str) -> str | None:
    return next((h for h in links(html) if _ZIP_MUNICIPIOS.match(h)), None)


def descobrir_url(edicao: int, ler=ler) -> str:
    """URL do zip nacional de municípios: Brasil/ (2023+) ou Brasil/BR/ (até 2022)."""
    for sub in ("Brasil/", "Brasil/BR/"):
        base = f"{MALHAS}/municipio_{edicao}/{sub}"
        try:
            nome = zip_municipios(ler(base))
        except OSError:
            continue
        if nome:
            return base + nome
    if edicao in MANIFESTO:
        return f"{MALHAS}/{MANIFESTO[edicao]}"
    raise LookupError(f"zip nacional de municípios não encontrado para {edicao}")
