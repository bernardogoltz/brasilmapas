"""Censo 2022 intramunicipal: URLs, tabelas e faixa de contagem (sem rede)."""

from ibge import censo2022


def test_camadas_e_urls():
    assert censo2022.CAMADAS == ["setores", "bairros", "distritos", "subdistritos"]
    assert censo2022.url("setores").endswith("/censo_2022/setores/shp/BR/BR_setores_CD2022.zip")
    assert censo2022.url("bairros").startswith("https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/")


def test_tabela_raw():
    assert censo2022.tabela("subdistritos") == "raw.censo2022_subdistritos"


def test_faixa_um_por_cento():
    lo, hi = censo2022.faixa("setores")
    assert lo < 468_099 < hi and hi - lo < 10_000


def test_dag_usa_modulo_e_asset():
    from pathlib import Path
    src = (Path(__file__).parent.parent / "airflow" / "dags" / "ibge_censo2022_intramunicipal.py").read_text()
    assert "schedule=None" in src and 'Asset("raw.censo2022")' in src
    assert "baixar.expand(camada=censo2022.CAMADAS)" in src
