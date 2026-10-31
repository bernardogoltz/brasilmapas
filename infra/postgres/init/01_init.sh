#!/usr/bin/env bash
# Roda uma vez, na criação do volume: bancos, papéis, extensões e schemas.
set -euo pipefail

psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres <<SQL
CREATE ROLE airflow     LOGIN PASSWORD '$AIRFLOW_DB_PASSWORD';
CREATE ROLE loader      LOGIN PASSWORD '$LOADER_PASSWORD';
CREATE ROLE transformer LOGIN PASSWORD '$TRANSFORMER_PASSWORD';
CREATE ROLE api_reader  LOGIN PASSWORD '$API_READER_PASSWORD';

CREATE DATABASE airflow OWNER airflow;
CREATE DATABASE geo;
REVOKE ALL ON DATABASE geo FROM PUBLIC;
GRANT CONNECT ON DATABASE geo TO loader, transformer, api_reader;
SQL

psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d geo <<'SQL'
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- raw: escrito pelo loader, lido pelo dbt
CREATE SCHEMA raw AUTHORIZATION loader;
GRANT USAGE ON SCHEMA raw TO transformer;
ALTER DEFAULT PRIVILEGES FOR ROLE loader IN SCHEMA raw GRANT SELECT ON TABLES TO transformer;

-- camadas do dbt
CREATE SCHEMA staging      AUTHORIZATION transformer;
CREATE SCHEMA intermediate AUTHORIZATION transformer;
CREATE SCHEMA marts        AUTHORIZATION transformer;
CREATE SCHEMA obs          AUTHORIZATION transformer;

-- meta: cargas (loader) e publicação (transformer)
CREATE SCHEMA meta AUTHORIZATION transformer;
GRANT USAGE, CREATE ON SCHEMA meta TO loader;

-- api_reader só lê marts e meta
GRANT USAGE ON SCHEMA marts, meta TO api_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE transformer IN SCHEMA marts, meta GRANT SELECT ON TABLES TO api_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE loader      IN SCHEMA meta        GRANT SELECT ON TABLES TO api_reader, transformer;
SQL
