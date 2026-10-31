"""Malhas territoriais do IBGE: consultas aos marts (GeoDataFrames) e desenho da UF a partir de GeoJSON estático.

Imports preguiçosos: `geoibge.mapa()`/`svg()` não carregam geopandas nem psycopg.
"""

from importlib import import_module

_ORIGEM = {
    "conectar": "core", "edicoes": "core", "municipios": "core", "reverse": "core", "ufs": "core", "validar": "core",
    "cep_para_municipio": "desenho", "mapa": "desenho", "svg": "desenho",
}
__all__ = sorted(_ORIGEM)


def __getattr__(nome: str):
    if nome in _ORIGEM:
        return getattr(import_module(f"geoibge.{_ORIGEM[nome]}"), nome)
    if nome in ("core", "desenho", "cli"):
        return import_module(f"geoibge.{nome}")
    raise AttributeError(f"module 'geoibge' has no attribute {nome!r}")
