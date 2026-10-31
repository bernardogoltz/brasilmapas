"""geoibge: normalização da entrada (sem banco) e, se o PostGIS local responder, consultas reais."""

import math

import pandas as pd
import pytest

import geoibge as gi
from geoibge.cli import separar
from geoibge.core import SQL_RESOLVER, SQL_REVERSE, normalizar_municipio, normalizar_pontos, normalizar_uf


@pytest.mark.parametrize("item, esperado", [
    ("SP", ("sigla", "SP")), (" rj ", ("sigla", "RJ")), (35, ("codigo", "35")), ("53", ("codigo", "53")),
])
def test_normalizar_uf(item, esperado):
    assert normalizar_uf(item) == esperado


@pytest.mark.parametrize("item", ["XX", "99", 7, "São Paulo"])
def test_normalizar_uf_invalida(item):
    with pytest.raises(ValueError, match="UF inválida"):
        normalizar_uf(item)


@pytest.mark.parametrize("item, esperado", [
    (3550308, ("cd7", "3550308", None)),
    ("330455", ("cd6", "330455", None)),
    (("Bom Jesus", "pi"), ("nome", "Bom Jesus", "PI")),
])
def test_normalizar_municipio(item, esperado):
    assert normalizar_municipio(item) == esperado


@pytest.mark.parametrize("item", ["12345", "abc", ("Bom Jesus", 22), ("a", "b", "c")])
def test_normalizar_municipio_invalido(item):
    with pytest.raises(ValueError):
        normalizar_municipio(item)


def test_normalizar_pontos_formas():
    um = normalizar_pontos((-23.55, -46.63))
    assert list(um[["lat", "lon"]].iloc[0]) == [-23.55, -46.63] and um.erro.isna().all()
    lista = normalizar_pontos([(-23.55, -46.63), (95, 0), (math.nan, 0)])
    assert lista.erro.tolist() == [None, "coordenada_invalida", "coordenada_invalida"]
    df = pd.DataFrame({"y": [-10.0], "x": [-50.0]}, index=["a"])
    assert normalizar_pontos(df, lat="y", lon="x").index.tolist() == ["a"]


def test_cli_separa_ufs_de_municipios():
    assert separar(["SP", "35", "3550308", "330455"]) == (["SP", "35"], ["3550308", "330455"])


def test_sql_reverse_usa_lookup_subdividido_e_lote():
    assert "marts.lkp_municipio" in SQL_REVERSE and "unnest(" in SQL_REVERSE
    assert "st_makepoint(lon, lat)" in SQL_REVERSE  # (x, y) = (lon, lat)
    assert "unaccent" in SQL_RESOLVER


def _banco_disponivel() -> bool:
    try:
        gi.conectar().execute("select 1 from marts.lkp_municipio limit 1")
        return True
    except Exception:
        return False


banco = pytest.mark.skipif(not _banco_disponivel(), reason="PostGIS local com marts indisponível")


@banco
def test_municipios_ordem_pedida_e_erros():
    m = gi.municipios(["330455", ("São Paulo", "SP")], resolucao="baixa")
    assert m.cd_mun.tolist() == ["3304557", "3550308"] and m.crs.to_epsg() == 4674
    with pytest.raises(ValueError, match="inexistente"):
        gi.municipios(["9999999"])


@banco
def test_ufs_e_validar():
    u = gi.ufs(["SP", 33])
    assert u.sg_uf.tolist() == ["SP", "RJ"]
    assert gi.validar(u).ok.all()


@banco
def test_reverse_pontos_de_referencia():
    r = gi.reverse([(-23.5503, -46.6339), (-15.7939, -47.8828), (0, 0)])
    assert r.cd_mun.tolist()[:2] == ["3550308", "5300108"]
    assert r.erro.tolist()[2] == "fora_do_brasil"
