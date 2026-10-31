"""Projeto dbt: parse sem banco e ligação dos assets entre ingestão e transformação."""

import json
import re
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).parent.parent
DBT = RAIZ / "dbt"
DAGS = RAIZ / "airflow" / "dags"


@pytest.fixture(scope="module")
def manifest(tmp_path_factory):
    alvo = tmp_path_factory.mktemp("dbt_target")
    r = subprocess.run(
        ["dbt", "parse", "--profiles-dir", ".", "--target-path", str(alvo), "--no-partial-parse"],
        cwd=DBT, capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads((alvo / "manifest.json").read_text())


def _modelos(manifest):
    return {n["name"]: n for n in manifest["nodes"].values() if n["resource_type"] == "model"}


def test_modelos_por_camada(manifest):
    esperado = {
        "staging": {"stg_ibge__municipios", "stg_ibge__localidades_municipios", "stg_ibge__localidades_estados",
                    "stg_ibge__setores_2022", "stg_ibge__bairros_2022", "stg_ibge__distritos_2022", "stg_ibge__subdistritos_2022"},
        "intermediate": {"int_municipios__geom_valida", "int_municipios__hierarquia", "int_municipios__simplificado"},
        "marts": {"dim_municipio", "geo_municipio", "geo_uf", "lkp_municipio", "geo_bairro", "geo_distrito", "lkp_setor"},
        "obs": {"obs_setores_divergentes", "obs_divergencia_setores"},
        "meta": {"publicacao"},
    }
    modelos = _modelos(manifest)
    for schema, nomes in esperado.items():
        assert nomes <= set(modelos), nomes - set(modelos)
        assert {modelos[n]["schema"] for n in nomes} == {schema}


def test_marts_tem_testes_de_chave_e_geometria(manifest):
    testes = [n for n in manifest["nodes"].values() if n["resource_type"] == "test"]
    por_modelo = {}
    for t in testes:
        for dep in t["depends_on"]["nodes"]:
            por_modelo.setdefault(dep.split(".")[-1], set()).add(t["test_metadata"]["name"] if t.get("test_metadata") else t["name"])
    assert {"chave_unica", "geometria_valida", "srid", "cobertura_valida"} <= por_modelo["geo_municipio"]
    assert {"chave_unica", "geometria_valida", "srid"} <= por_modelo["geo_uf"]
    assert {"assert_contagem_municipios_api", "assert_cobertura_api_localidades"} <= por_modelo["dim_municipio"]
    assert "assert_simplificacao_nao_piora_cobertura" in por_modelo["geo_municipio"]
    assert {"geometria_valida", "srid", "assert_lkp_cobre_ponto_interno"} <= por_modelo["lkp_municipio"]
    assert {"geometria_valida", "srid", "assert_lkp_setor_cobre_ponto_interno"} <= por_modelo["lkp_setor"]
    assert {"unique", "not_null"} <= por_modelo["stg_ibge__bairros_2022"]


def test_seed_areas_operacionais():
    linhas = (DBT / "seeds" / "areas_operacionais.csv").read_text().splitlines()
    assert linhas[0] == "cd_mun,nm_area" and {l[:7] for l in linhas[1:]} == {"4300001", "4300002"}


def test_assets_da_ingestao_disparam_o_dbt():
    def assets(arquivo):
        return set(re.findall(r'Asset\("([^"]+)"\)', (DAGS / arquivo).read_text()))

    produzidos = assets("ibge_malha_municipal.py") | assets("ibge_localidades.py") | assets("ibge_censo2022_intramunicipal.py")
    dbt_dag = (DAGS / "dbt_geo.py").read_text()
    assert assets("dbt_geo.py") == produzidos == {"raw.malha_municipal", "raw.localidades", "raw.censo2022"}
    assert "schedule=RAW_MALHA | RAW_LOCALIDADES | RAW_CENSO" in dbt_dag


def test_localidades_atualiza_asset_uma_vez():
    src = (DAGS / "ibge_localidades.py").read_text()
    assert src.count("outlets=[RAW_LOCALIDADES]") == 1
    assert "@task(outlets=[RAW_LOCALIDADES])\n    def publicar" in src
