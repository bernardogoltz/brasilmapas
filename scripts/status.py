# /// script
# requires-python = ">=3.12"
# dependencies = ["rich>=14"]
# ///
"""Painel dos serviços do Docker Compose (make status)."""

import json
import subprocess

from rich.console import Console
from rich.table import Table


def sh(*args: str) -> str:
    return subprocess.run(args, capture_output=True, text=True).stdout


def jsonl(out: str) -> list[dict]:
    return [json.loads(line) for line in out.splitlines() if line.strip()]


ICONE = {"healthy": "[green]●[/]", "starting": "[yellow]◐[/]", "unhealthy": "[red]●[/]"}


def main() -> None:
    servicos = sh("docker", "compose", "--profile", "*", "config", "--services").split()
    containers = {c["Service"]: c for c in jsonl(sh("docker", "compose", "ps", "-a", "--format", "json"))}
    ativos = [c["Name"] for c in containers.values() if c["State"] == "running"]
    stats = {x["Name"]: x for x in jsonl(sh("docker", "stats", "--no-stream", "--format", "json", *ativos))} if ativos else {}

    t = Table.grid(padding=(0, 2))
    for s in sorted(servicos, key=lambda s: s not in containers):
        c = containers.get(s)
        if c is None or c["State"] != "running":
            t.add_row("[dim]○[/]", f"[dim]{s}[/]", "")
            continue
        porta = next((f":{p['PublishedPort']}" for p in c.get("Publishers") or [] if p["PublishedPort"]), "")
        st = stats.get(c["Name"], {})
        tempo = c["RunningFor"].replace(" ago", "").replace("About ", "~")
        t.add_row(
            ICONE.get(c.get("Health", ""), "[green]●[/]"), s, f"[dim]{porta}[/]",
            f"[dim]{tempo}[/]", f"[dim]{st.get('CPUPerc', '')}[/]", f"[dim]{st.get('MemUsage', '').split(' / ')[0]}[/]",
        )
    Console().print(t)


if __name__ == "__main__":
    main()
