"""dbt build (staging → marts) via Cosmos, disparado quando a ingestão atualiza um asset do raw.

Cada modelo vira um task group com `run` e `test`; um teste com erro barra os modelos seguintes.
"""

import os
from datetime import datetime
from pathlib import Path

from airflow.sdk import Asset
from cosmos import DbtDag, ExecutionConfig, ProfileConfig, ProjectConfig, RenderConfig
from cosmos.constants import LoadMode, TestBehavior

DBT_DIR = Path(os.environ.get("GEO_DBT_DIR", "/opt/airflow/dbt"))
DBT_BIN = Path(os.environ.get("GEO_DBT_BIN", "/opt/airflow/dbt_venv/bin/dbt"))

# mesmos assets que os outlets de ibge_malha_municipal, ibge_localidades e ibge_censo2022_intramunicipal
RAW_MALHA = Asset("raw.malha_municipal")
RAW_LOCALIDADES = Asset("raw.localidades")
RAW_CENSO = Asset("raw.censo2022")

dbt_geo = DbtDag(
    dag_id="dbt_geo",
    project_config=ProjectConfig(DBT_DIR),
    profile_config=ProfileConfig(profile_name="geo", target_name="dev", profiles_yml_filepath=DBT_DIR / "profiles.yml"),
    execution_config=ExecutionConfig(dbt_executable_path=DBT_BIN),
    render_config=RenderConfig(load_method=LoadMode.DBT_LS, test_behavior=TestBehavior.AFTER_EACH),
    schedule=RAW_MALHA | RAW_LOCALIDADES | RAW_CENSO,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    is_paused_upon_creation=False,
    max_active_runs=1,
    default_args={"retries": 1},
    tags=["dbt", "transformacao"],
)
