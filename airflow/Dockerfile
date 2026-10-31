FROM apache/airflow:3.3.2-python3.12

USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends gdal-bin \
 && rm -rf /var/lib/apt/lists/*

USER airflow
RUN pip install --no-cache-dir "apache-airflow[statsd]==${AIRFLOW_VERSION}" "pyogrio>=0.13.0" "astronomer-cosmos==1.15.1"

# dbt num virtualenv próprio, como o Cosmos recomenda (não conflita com as dependências do Airflow)
RUN python -m venv /opt/airflow/dbt_venv \
 && /opt/airflow/dbt_venv/bin/pip install --no-cache-dir "dbt-core==1.12.6" "dbt-postgres==1.11.0"
