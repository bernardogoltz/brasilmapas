FROM apache/airflow:3.3.2-python3.12

USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends gdal-bin \
 && rm -rf /var/lib/apt/lists/*

USER airflow
RUN pip install --no-cache-dir "apache-airflow==${AIRFLOW_VERSION}" "pyogrio>=0.13.0"
