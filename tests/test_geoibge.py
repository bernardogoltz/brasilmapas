"""geoibge: normalização da entrada (sem banco) e, se o PostGIS local responder, consultas reais."""

import math

import pandas as pd
import pytest

import geoibge as gi
from geoibge.cli import separar
from types import SimpleNamespace

from geoibge.core import SQL_RESOLVER, _avisos, normalizar_municipio, normalizar_pontos, normalizar_uf, sql_reverse


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
    sql = sql_reverse()
    assert "marts.lkp_municipio" in sql and "unnest(" in sql
    assert "st_makepoint(lon, lat)" in sql  # (x, y) = (lon, lat)
    assert "unaccent" in SQL_RESOLVER


def test_sql_reverse_com_e_sem_setores():
    com, sem = sql_reverse(True), sql_reverse(False)
    assert "marts.lkp_setor" in com and "s.cd_dist" in com and "s.nm_bairro" in com
    assert "lkp_setor" not in sem and "{" not in sem


def _linha(**kw):
    base = dict(proximo=False, cd_mun="3550308", cd_setor="355030878000001", cd_mun_setor="3550308", cd_bairro=None,
                cd_dist="355030878")
    return SimpleNamespace(**{**base, **kw})


def test_avisos_do_reverse():
    assert _avisos(_linha()) == "sem bairro na malha 2022; distrito informado"
    assert _avisos(_linha(cd_bairro="3304557001001")) is None
    assert _avisos(_linha(cd_mun="4300001", cd_mun_setor="4300001", cd_dist=None)) is None  # lagoa
    assert "malha mudou" in _avisos(_linha(cd_mun="5101837", cd_mun_setor="5101803", cd_bairro="x"))
    assert _avisos(_linha(cd_setor=float("nan"))) == "sem setor 2022 no ponto"
    assert _avisos(_linha(proximo=True, cd_bairro="x")).startswith("fora da malha")
    assert _avisos(_linha(cd_mun=float("nan"), proximo=float("nan"))) is None


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


@banco
@pytest.mark.skipif(not (_banco_disponivel() and gi.core._tem_setores()), reason="lkp_setor indisponível")
def test_reverse_intramunicipal():
    r = gi.reverse([(-23.5503, -46.6339), (-22.9711, -43.1822)])
    assert r.cd_dist.tolist()[0] == "355030878" and r.nm_dist.tolist()[0] == "Sé"
    assert r.cd_bairro.isna().tolist() == [True, False]  # São Paulo não tem bairros; Rio tem (Copacabana)
    assert r.cd_setor.str.len().eq(15).all()
