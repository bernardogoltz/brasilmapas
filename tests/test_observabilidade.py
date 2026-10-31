"""Observabilidade: compose do profile obs, configs do Prometheus/StatsD e dashboards do Grafana (sem rede)."""

import json
import re
import subprocess
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).parent.parent
INFRA = RAIZ / "infra"
DASHBOARDS = sorted((INFRA / "grafana" / "dashboards").glob("*.json"))


@pytest.fixture(scope="module")
def compose():
    return yaml.safe_load((RAIZ / "docker-compose.yml").read_text())


def test_servicos_obs(compose):
    obs = {nome for nome, s in compose["services"].items() if "obs" in s.get("profiles", [])}
    assert obs == {"prometheus", "grafana", "statsd-exporter", "postgres-exporter"}


def test_volumes_apontam_para_arquivos_existentes(compose):
    for nome in ("prometheus", "grafana", "statsd-exporter"):
        for v in compose["services"][nome]["volumes"]:
            origem = v.split(":")[0]
            if origem.startswith("./"):
                assert (RAIZ / origem).exists(), f"{nome}: {origem}"


def test_airflow_envia_statsd_para_o_exporter(compose):
    env = compose["x-airflow"]["environment"]
    assert env["AIRFLOW__METRICS__STATSD_ON"] == "True"
    assert env["AIRFLOW__METRICS__STATSD_HOST"] == "statsd-exporter"
    assert "apache-airflow[statsd]" in (RAIZ / "airflow" / "Dockerfile").read_text()


def test_alvos_do_prometheus_sao_servicos_do_compose(compose):
    cfg = yaml.safe_load((INFRA / "prometheus" / "prometheus.yml").read_text())
    alvos = [t for job in cfg["scrape_configs"] for sc in job["static_configs"] for t in sc["targets"]]
    for alvo in alvos:
        host = alvo.split(":")[0]
        assert host == "localhost" or host in compose["services"], alvo


def test_mapping_statsd_usa_todos_os_grupos():
    cfg = yaml.safe_load((INFRA / "statsd" / "mapping.yml").read_text())
    for m in cfg["mappings"]:
        assert m["match"].startswith("airflow.")
        grupos = m["match"].count("*")
        usados = {int(g) for v in m.get("labels", {}).values() for g in re.findall(r"\$(\d)", v)}
        assert usados == set(range(1, grupos + 1)), m["match"]


def test_datasources_tem_uids_usados_nos_dashboards():
    ds = yaml.safe_load((INFRA / "grafana" / "provisioning" / "datasources" / "datasources.yml").read_text())
    uids = {d["uid"] for d in ds["datasources"]}
    assert uids == {"prometheus", "geo-pg"}
    for arq in DASHBOARDS:
        for p in json.loads(arq.read_text())["panels"]:
            assert p["datasource"]["uid"] in uids, (arq.name, p["title"])


@pytest.mark.parametrize("arq", DASHBOARDS, ids=lambda p: p.name)
def test_dashboard_bem_formado(arq):
    d = json.loads(arq.read_text())
    assert d["uid"] == arq.stem
    ids = [p["id"] for p in d["panels"]]
    assert len(ids) == len(set(ids))
    for p in d["panels"]:
        g = p["gridPos"]
        assert g["x"] + g["w"] <= 24, p["title"]
        alvo = p["targets"][0]
        assert alvo.get("expr") or alvo.get("rawSql"), p["title"]


def test_dashboards_esperados():
    assert {a.stem for a in DASHBOARDS} == {"geo-pipeline", "geo-qualidade", "geo-banco"}


def test_sql_dos_dashboards_le_so_o_que_o_monitor_pode():
    # o papel monitor só tem SELECT em meta, obs e marts (+ pg_stat_statements via pg_monitor)
    permitidos = {"meta", "obs", "marts"}
    for arq in DASHBOARDS:
        for p in json.loads(arq.read_text())["panels"]:
            sql = p["targets"][0].get("rawSql", "")
            for schema in re.findall(r"\b(?:from|join)\s+([a-z_]+)\.", sql):
                assert schema in permitidos, (arq.name, p["title"], schema)


def test_init_do_monitor_concede_os_schemas():
    sh = (INFRA / "postgres" / "init" / "02_monitor.sh").read_text()
    assert "IF NOT EXISTS" in sh  # idempotente: `make obs` roda de novo em volumes antigos
    assert "GRANT pg_monitor TO monitor" in sh
    assert "SCHEMA meta, obs, marts" in sh
    r = subprocess.run(["bash", "-n", str(INFRA / "postgres" / "init" / "02_monitor.sh")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_makefile_tem_obs_e_tour():
    mk = (RAIZ / "Makefile").read_text()
    assert re.search(r"^obs: .*## ", mk, re.M)
    assert re.search(r"^tour: .*## ", mk, re.M)
    assert (RAIZ / "notebooks" / "06_tour.py").exists()
