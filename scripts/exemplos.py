# /// script
# requires-python = ">=3.12"
# dependencies = ["rich>=14", "psycopg[binary]>=3.2"]
# ///
"""Exemplos do README (make exemplos): código IBGE → SVG da UF, e o tempo de cada caminho.

Três caminhos para o mesmo desenho:
- banco: uma consulta aos marts (gold) com `ST_AsSVG`, sem cache, a cada pedido;
- GeoJSON por UF (`src/geoibge/mapas/`): `geoibge.svg()`, 1ª chamada da UF e com cache;
- `data/mapas.json`: paths prontos, só concatenação de strings (a receita do README).

Grava os mapas em `docs/img/` e o print da tabela de tempos em `docs/img/tempos.svg`.
"""

import html
import json
import os
import statistics
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from geoibge import desenho  # noqa: E402  (só stdlib: não carrega geopandas)

DESTINO = RAIZ / "docs" / "img"
DSN_PADRAO = "postgresql://api_reader:api_reader@localhost:5432/geo"
# código → por que está na galeria
GALERIA = {
    "3550308": "capital grande",
    "4314902": "lagoas do RS (água)",
    "1302603": "UF extensa",
    "3106200": "MG, o maior arquivo",
    "2927408": "litoral",
    "2605459": "pequeno: ganha círculo",
}
MEDIDOS = ["3550308", "3106200", "1302603", "5300108"]

# Uma ida ao banco por pedido: contorno da UF + todos os municípios, projetados e já como `d` do SVG.
# ST_AsSVG inverte o y; a afim leva lon/lat para a mesma escala do svg() (lado maior = lado_px).
SQL_SVG = """
with uf as (
    select u.cd_uf, u.sg_uf, u.geom_media as geom,
           st_xmin(u.geom_media) as xmin, st_ymax(u.geom_media) as ymax,
           cos(radians((st_ymin(u.geom_media) + st_ymax(u.geom_media)) / 2)) as c,
           %(lado)s / greatest((st_xmax(u.geom_media) - st_xmin(u.geom_media))
                                 * cos(radians((st_ymin(u.geom_media) + st_ymax(u.geom_media)) / 2)),
                               st_ymax(u.geom_media) - st_ymin(u.geom_media)) as k,
           st_ymax(u.geom_media) - st_ymin(u.geom_media) as dy,
           st_xmax(u.geom_media) - st_xmin(u.geom_media) as dx
    from marts.geo_uf u
    where u.edicao = %(edicao)s and u.cd_uf = %(cd_uf)s
),
f as (
    select null::text as cd_mun, null::text as nome, true as is_municipio, uf.geom from uf
    union all
    select g.cd_mun, d.nm_mun, d.is_municipio, g.geom_media
    from marts.geo_municipio g
    join marts.dim_municipio d using (edicao, cd_mun)
    where g.edicao = %(edicao)s and d.cd_uf = %(cd_uf)s
)
select f.cd_mun, f.nome, f.is_municipio, uf.sg_uf,
       round((uf.dx * uf.c * uf.k)::numeric, 1)::float as largura, round((uf.dy * uf.k)::numeric, 1)::float as altura,
       st_assvg(st_affine(f.geom, uf.c * uf.k, 0, 0, uf.k, -uf.xmin * uf.c * uf.k, -uf.ymax * uf.k), 0, 1) as d
from f cross join uf
order by f.cd_mun nulls first
"""


def montar(cod: str, uf: dict, largura: int = 600) -> str:
    """SVG pela receita de `data/mapas.json`; `uf` é `ufs[cd_uf]` do catálogo (ou o mesmo formato vindo do banco)."""
    cores, raio = desenho.CORES, desenho.RAIO_MARCADOR
    mun, w, h, m = uf["municipios"][cod], uf["largura"], uf["altura"], raio + 4
    s = 'fill-rule="evenodd" vector-effect="non-scaling-stroke"'

    def ds(nivel):
        return "".join(x["d"] for x in uf["municipios"].values() if x["nivel"] == nivel)

    partes = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-m} {-m} {w + 2 * m:.1f} {h + 2 * m:.1f}" '
        f'width="{largura}" height="{round(largura * (h + 2 * m) / (w + 2 * m))}">',
        f"<title>{html.escape(mun['nome'])} ({uf['sigla']})</title>",
        f'<path d="{ds("municipio")}" fill="{cores["fundo"]}" stroke="{cores["borda"]}" stroke-width="0.5" {s}/>',
        f'<path d="{ds("area_operacional")}" fill="{cores["agua"]}" {s}/>',
        f'<path d="{mun["d"]}" fill="{cores["destaque"]}" stroke="{cores["destaque"]}" stroke-width="0.5" {s}/>',
        f'<path d="{uf["contorno"]}" fill="none" stroke="{cores["uf"]}" stroke-width="1.2" {s}/>',
    ]
    if "caixa" in mun:
        x0, y0, x1, y1 = mun["caixa"]
        if max(x1 - x0, y1 - y0) < raio:
            partes.append(f'<circle cx="{(x0 + x1) / 2:.1f}" cy="{(y0 + y1) / 2:.1f}" r="{raio}" fill="none" '
                          f'stroke="{cores["destaque"]}" stroke-width="2" {s}/>')
    return "\n".join(partes + ["</svg>"])


def uf_do_banco(linhas: list[dict]) -> dict:
    """Linhas do SQL_SVG (a 1ª, cd_mun nulo, é o contorno) → mesmo formato de `ufs[cd_uf]` do catálogo."""
    contorno, *municipios = linhas
    return {"sigla": contorno["sg_uf"], "largura": contorno["largura"], "altura": contorno["altura"],
            "contorno": contorno["d"],
            "municipios": {r["cd_mun"]: {"nome": r["nome"], "d": r["d"],
                                         "nivel": "municipio" if r["is_municipio"] else "area_operacional"}
                           for r in municipios}}


def svg_banco(conn, cod: str, edicao: int, largura: int = 600) -> str:
    with conn.cursor() as cur:
        cur.execute(SQL_SVG, {"cd_uf": cod[:2], "edicao": edicao, "lado": desenho.LADO_PX})
        nomes = [c.name for c in cur.description]
        linhas = [dict(zip(nomes, r)) for r in cur.fetchall()]
    return montar(cod, uf_do_banco(linhas), largura)


def mediana_ms(funcao, n: int, antes=None) -> float:
    """Mediana de `n` execuções, em ms; `antes()` roda fora do cronômetro (ex.: limpar cache)."""
    tempos = []
    for _ in range(n):
        if antes:
            antes()
        t0 = time.perf_counter()
        funcao()
        tempos.append((time.perf_counter() - t0) * 1000)
    return statistics.median(tempos)


def limpar_cache():
    for cache in (desenho._uf, desenho._indice, desenho._desenho):
        cache.cache_clear()


def fmt(ms: float) -> str:
    return f"{ms:.2f} ms" if ms < 10 else f"{ms:.0f} ms"


def main() -> None:
    import psycopg
    from rich.console import Console
    from rich.table import Table

    console = Console(record=True, width=124, highlight=False)
    DESTINO.mkdir(parents=True, exist_ok=True)
    for cod in GALERIA:
        (DESTINO / f"{cod}.svg").write_text(desenho.svg(cod, largura=300), encoding="utf-8")

    conn = psycopg.connect(os.environ.get("GEOIBGE_DSN", DSN_PADRAO), autocommit=True)
    with conn.cursor() as cur:
        cur.execute("select max(edicao) from meta.publicacao")
        edicao = cur.fetchone()[0]
    (DESTINO / "3550308_banco.svg").write_text(svg_banco(conn, "3550308", edicao, 300), encoding="utf-8")

    t0 = time.perf_counter()
    catalogo = json.loads(desenho.JSON_PUBLICO.read_bytes())
    carga_catalogo = (time.perf_counter() - t0) * 1000

    tabela = Table(title=f"código IBGE → SVG da UF com o município em destaque (malha {edicao}; mediana)")
    tabela.add_column("código")
    tabela.add_column("município", no_wrap=True)
    tabela.add_column("mun. na UF", justify="right")
    tabela.add_column("banco (gold)", justify="right", style="red")
    tabela.add_column("GeoJSON 1ª vez", justify="right", style="yellow")
    tabela.add_column("GeoJSON cache", justify="right", style="green")
    tabela.add_column("mapas.json", justify="right", style="green")
    tabela.add_column("KB banco/JSON", justify="right")
    for cod in MEDIDOS:
        uf = catalogo["ufs"][cod[:2]]
        svg_banco(conn, cod, edicao)  # aquece o cache do Postgres
        banco = mediana_ms(lambda: svg_banco(conn, cod, edicao), 15)
        frio = mediana_ms(lambda: desenho.svg(cod), 7, antes=limpar_cache)
        quente = mediana_ms(lambda: desenho.svg(cod), 200)
        json_ms = mediana_ms(lambda: montar(cod, uf), 200)
        kb = len(svg_banco(conn, cod, edicao)) / 1024, len(montar(cod, uf)) / 1024
        tabela.add_row(cod, f"{uf['municipios'][cod]['nome']} ({uf['sigla']})", str(len(uf["municipios"])),
                       fmt(banco), fmt(frio), fmt(quente), fmt(json_ms), f"{kb[0]:.0f} / {kb[1]:.0f}")
    conn.close()

    console.print(tabela)
    console.print(f"[dim]data/mapas.json: carga única de todas as UFs em {fmt(carga_catalogo)}; banco = 1 consulta "
                  "aos marts (geom_media + ST_AsSVG) por pedido, conexão já aberta.[/]")
    console.save_svg(str(DESTINO / "tempos.svg"), title="make exemplos")
    console.print(f"gravado em {DESTINO.relative_to(RAIZ)}/")


if __name__ == "__main__":
    main()
