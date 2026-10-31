"""Malhas territoriais do IBGE a partir dos marts do PostGIS, como GeoDataFrames."""

from geoibge.core import conectar, edicoes, municipios, reverse, ufs, validar

__all__ = ["conectar", "edicoes", "municipios", "reverse", "ufs", "validar"]
