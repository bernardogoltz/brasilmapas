"""Carga no raw: comando ogr2ogr e SQL de meta.cargas."""

from pathlib import Path

SQL_META = Path(__file__).with_name("sql") / "meta_cargas.sql"

INSERIR_CARGA = """
INSERT INTO meta.cargas (fonte, edicao, url, sha256, bytes, feicoes, duracao_s)
VALUES (%(fonte)s, %(edicao)s, %(url)s, %(sha256)s, %(bytes)s, %(feicoes)s, %(duracao_s)s)
"""

JA_CARREGADA = "SELECT sha256 FROM meta.cargas WHERE fonte = %s AND edicao = %s ORDER BY carregado_em DESC LIMIT 1"


def dsn_ogr(host: str, port: int, dbname: str, user: str, password: str) -> str:
    return f"PG:host={host} port={port} dbname={dbname} user={user} password={password}"


def ogr2ogr_cmd(zip_path: Path, camada: str, edicao: int, tabela: str, dsn: str) -> list[str]:
    """Lê o shapefile de dentro do zip e anexa em `tabela`, marcando `_edicao` em cada linha."""
    return [
        "ogr2ogr", "-f", "PostgreSQL", dsn,
        f"/vsizip/{Path(zip_path).resolve()}",
        "-dialect", "SQLITE",
        "-sql", f'SELECT *, {int(edicao)} AS _edicao FROM "{camada}"',
        "-nln", tabela, "-append", "-addfields",
        "-nlt", "PROMOTE_TO_MULTI", "-lco", "GEOMETRY_NAME=geom",
        "--config", "PG_USE_COPY", "YES",
    ]


def apagar_edicao(tabela: str, edicao: int) -> str:
    """DELETE da edição, só se a tabela já existe (primeira carga cria a tabela)."""
    schema, nome = tabela.split(".")
    return (
        f"DO $$ BEGIN IF to_regclass('{schema}.{nome}') IS NOT NULL THEN "
        f"DELETE FROM {schema}.{nome} WHERE _edicao = {int(edicao)}; END IF; END $$"
    )
