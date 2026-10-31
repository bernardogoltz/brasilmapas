"""Malha municipal do IBGE: descobrir edição → baixar → validar → carregar raw.br_municipios.

Backfill: disparar com {"edicao": 2019}; {"forcar": true} recarrega uma edição já carregada.
"""

import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.sdk import Asset, Param, dag, get_current_context, task

from ibge import carga, download, geoftp, validar

CONN = "geo_loader"
TABELA = "raw.br_municipios"
DATA = Path(os.environ.get("GEO_DATA_DIR", "/opt/airflow/data"))
RAW_MALHA = Asset("raw.malha_municipal")


@dag(
    schedule="@monthly",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    is_paused_upon_creation=False,
    max_active_runs=1,
    default_args={"retries": 2},
    params={
        "edicao": Param(None, type=["null", "integer"], description="vazio = mais recente no geoftp"),
        "forcar": Param(False, type="boolean", description="recarrega mesmo se já carregada"),
    },
    tags=["ibge", "ingestao"],
)
def ibge_malha_municipal():
    @task
    def descobrir() -> dict:
        edicao = get_current_context()["params"]["edicao"]
        if edicao is None:
            edicao = geoftp.edicoes(geoftp.ler(geoftp.MALHAS + "/"))[-1]
        return {"edicao": int(edicao), "url": geoftp.descobrir_url(int(edicao))}

    @task.short_circuit
    def precisa_carregar(alvo: dict) -> bool:
        hook = PostgresHook(CONN)
        hook.run(carga.SQL_META.read_text())
        carregada = hook.get_first(carga.JA_CARREGADA, parameters=("malha_municipal", alvo["edicao"]))
        return bool(get_current_context()["params"]["forcar"]) or carregada is None

    @task(retries=3)
    def baixar(alvo: dict) -> dict:
        destino = DATA / "raw" / "malha_municipal" / str(alvo["edicao"]) / alvo["url"].rsplit("/", 1)[1]
        res = download.baixar(alvo["url"], destino, download.tamanho_remoto(alvo["url"]))
        return {**res, "caminho": str(destino)}

    @task(retries=0)
    def validar_zip(arq: dict) -> dict:
        return validar.validar_zip(Path(arq["caminho"]))

    @task(outlets=[RAW_MALHA])
    def carregar(alvo: dict, arq: dict, val: dict) -> None:
        hook = PostgresHook(CONN)
        c = hook.get_connection(CONN)
        inicio = time.monotonic()
        hook.run(carga.apagar_edicao(TABELA, alvo["edicao"]))
        dsn = carga.dsn_ogr(c.host, c.port or 5432, c.schema, c.login, c.password)
        subprocess.run(carga.ogr2ogr_cmd(Path(arq["caminho"]), val["camada"], alvo["edicao"], TABELA, dsn), check=True)
        hook.run(carga.INSERIR_CARGA, parameters={
            "fonte": "malha_municipal", "edicao": alvo["edicao"], "url": alvo["url"],
            "sha256": arq["sha256"], "bytes": arq["bytes"], "feicoes": val["feicoes"],
            "duracao_s": round(time.monotonic() - inicio, 2),
        })

    alvo = descobrir()
    arq = baixar(alvo)
    precisa_carregar(alvo) >> arq
    carregar(alvo, arq, validar_zip(arq))


ibge_malha_municipal()
