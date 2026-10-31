#!/usr/bin/env bash
# Papel monitor (Grafana e postgres-exporter): estatísticas do servidor e leitura de meta, obs e marts.
# Idempotente: roda na criação do volume e de novo em `make obs`, para volumes antigos.
set -euo pipefail

psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d geo <<SQL
DO \$\$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'monitor') THEN
    CREATE ROLE monitor LOGIN;
  END IF;
END \$\$;
ALTER ROLE monitor PASSWORD '$MONITOR_PASSWORD';
GRANT pg_monitor TO monitor;
GRANT CONNECT ON DATABASE geo TO monitor;

GRANT USAGE ON SCHEMA meta, obs, marts TO monitor;
GRANT SELECT ON ALL TABLES IN SCHEMA meta, obs, marts TO monitor;
ALTER DEFAULT PRIVILEGES FOR ROLE transformer IN SCHEMA meta, obs, marts GRANT SELECT ON TABLES TO monitor;
ALTER DEFAULT PRIVILEGES FOR ROLE loader      IN SCHEMA meta             GRANT SELECT ON TABLES TO monitor;
SQL
