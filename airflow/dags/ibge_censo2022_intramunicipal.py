"""Censo 2022 intramunicipal: setores, bairros, distritos e subdistritos → raw.censo2022_<camada>.

Dado estático: disparo manual. Uma camada já carregada com o mesmo sha256 é pulada; {"forcar": true} recarrega.
"""

import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

from airflow.exceptions import AirflowSkipException
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.sdk import Asset, Param, dag, get_current_context, task

from ibge import carga, censo2022, download, validar

CONN = "geo_loader"
DATA = Path(os.environ.get("GEO_DATA_DIR", "/opt/airflow/data"))
RAW_CENSO = Asset("raw.censo2022")


@dag(
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    is_paused_upon_creation=False,
    max_active_runs=1,
    default_args={"retries": 2},
    params={"forcar": Param(False, type="boolean", description="recarrega mesmo se o sha256 não mudou")},
    tags=["ibge", "ingestao", "censo2022"],
)
def ibge_censo2022_intramunicipal():
    @task(retries=3, max_active_tis_per_dag=2)
    def baixar(camada: str) -> dict:
        url = censo2022.url(camada)
        destino = DATA / "raw" / "censo2022" / camada / url.rsplit("/", 1)[1]
        res = download.baixar(url, destino, download.tamanho_remoto(url), timeout=900)
        return {**res, "camada": camada, "url": url, "caminho": str(destino)}

    @task(retries=0)
    def validar_zip(arq: dict) -> dict:
        val = validar.validar_zip(Path(arq["caminho"]), censo2022.faixa(arq["camada"]))
        return {**arq, "camada_shp": val["camada"], "feicoes": val["feicoes"]}

    @task
    def carregar(item: dict) -> int:
        camada, tabela = item["camada"], censo2022.tabela(item["camada"])
        hook = PostgresHook(CONN)
        hook.run(carga.SQL_META.read_text())
        fonte = f"censo2022_{camada}"
        anterior = hook.get_first(carga.JA_CARREGADA, parameters=(fonte, censo2022.EDICAO))
        if anterior and anterior[0] == item["sha256"] and not get_current_context()["params"]["forcar"]:
            return 0
        c = hook.get_connection(CONN)
        inicio = time.monotonic()
        hook.run(carga.apagar_edicao(tabela, censo2022.EDICAO))
        dsn = carga.dsn_ogr(c.host, c.port or 5432, c.schema, c.login, c.password)
        subprocess.run(carga.ogr2ogr_cmd(Path(item["caminho"]), item["camada_shp"], censo2022.EDICAO, tabela, dsn), check=True)
        hook.run(carga.INSERIR_CARGA, parameters={
            "fonte": fonte, "edicao": censo2022.EDICAO, "url": item["url"],
            "sha256": item["sha256"], "bytes": item["bytes"], "feicoes": item["feicoes"],
            "duracao_s": round(time.monotonic() - inicio, 2),
        })
        return item["feicoes"]

    @task(outlets=[RAW_CENSO])
    def publicar(contagens: list[int]) -> int:
        """Atualiza o asset uma vez, depois das quatro camadas (dispara o dbt_geo); nada novo, nada dispara."""
        if not sum(contagens):
            raise AirflowSkipException("nenhuma camada mudou")
        return sum(contagens)

    publicar(carregar.expand(item=validar_zip.expand(arq=baixar.expand(camada=censo2022.CAMADAS))))


ibge_censo2022_intramunicipal()
