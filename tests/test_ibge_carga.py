from pathlib import Path

from ibge import carga, localidades


def test_ogr2ogr_cmd_marca_edicao_e_anexa():
    cmd = carga.ogr2ogr_cmd(Path("/d/a.zip"), "BR_Municipios_2025", 2025, "raw.br_municipios", "PG:dbname=geo")
    assert cmd[0] == "ogr2ogr" and "/vsizip//d/a.zip" in cmd
    assert 'SELECT *, 2025 AS _edicao FROM "BR_Municipios_2025"' in cmd
    assert {"-append", "-addfields", "PROMOTE_TO_MULTI"} <= set(cmd)
    assert cmd[cmd.index("-nln") + 1] == "raw.br_municipios"


def test_apagar_edicao_condicional():
    sql = carga.apagar_edicao("raw.br_municipios", 2019)
    assert "to_regclass('raw.br_municipios')" in sql and "_edicao = 2019" in sql


def test_sql_meta_cria_tabela():
    sql = carga.SQL_META.read_text()
    assert "CREATE TABLE IF NOT EXISTS meta.cargas" in sql and "sha256" in sql


def test_localidades_tabela_e_linhas():
    assert localidades.tabela("regioes-imediatas") == "raw.localidades_regioes_imediatas"
    assert localidades.url("estados").endswith("/estados?view=nivelado")
    assert localidades.linhas([{"UF-nome": "São Paulo"}]) == [('{"UF-nome": "São Paulo"}',)]


def test_localidades_decodifica_json_e_gzip():
    import gzip
    corpo = b'[{"UF-id": 35}]'
    assert localidades.decodificar(corpo) == localidades.decodificar(gzip.compress(corpo)) == [{"UF-id": 35}]
