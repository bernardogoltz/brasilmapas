"""API Localidades do IBGE → raw.localidades_<nivel>: um retrato por dia, uma linha JSONB por item."""

import time
from datetime import datetime

from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.sdk import Asset, dag, task

from ibge import carga, localidades

CONN = "geo_loader"
RAW_LOCALIDADES = Asset("raw.localidades")


@dag(
    schedule="@weekly",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    is_paused_upon_creation=False,
    default_args={"retries": 3},
    tags=["ibge", "ingestao"],
)
def ibge_localidades():
    @task
    def coletar(nivel: str) -> int:
        inicio = time.monotonic()
        itens = localidades.buscar(nivel)
        tabela = localidades.tabela(nivel)
        hook = PostgresHook(CONN)
        hook.run(carga.SQL_META.read_text())
        with hook.get_conn() as conn, conn.cursor() as cur:
            cur.execute(localidades.ddl(nivel))
            cur.execute(f"DELETE FROM {tabela} WHERE coletado_em = current_date")
            cur.executemany(f"INSERT INTO {tabela} (coletado_em, dados) VALUES (current_date, %s)", localidades.linhas(itens))
            cur.execute(carga.INSERIR_CARGA, {
                "fonte": f"localidades_{nivel}", "edicao": None, "url": localidades.url(nivel),
                "sha256": None, "bytes": None, "feicoes": len(itens),
                "duracao_s": round(time.monotonic() - inicio, 2),
            })
        return len(itens)

    @task(outlets=[RAW_LOCALIDADES])
    def publicar(contagens: list[int]) -> int:
        """Atualiza o asset uma vez só, depois de todos os níveis (dispara o dbt_geo)."""
        return sum(contagens)

    publicar(coletar.expand(nivel=localidades.NIVEIS))


ibge_localidades()
