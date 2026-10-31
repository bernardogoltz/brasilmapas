# /// script
# requires-python = ">=3.12"
# dependencies = ["matplotlib>=3.9", "rich>=14"]
# ///
"""Série de códigos IBGE → SVG do matplotlib com os municípios pintados (make plots).

Desenha as UFs que a série toca (todos os municípios ao fundo, a série em destaque), a partir dos GeoJSON por UF
(`src/geoibge/mapas/`), sem banco nem rede. O título traz o tempo de execução: resolver os códigos, ler as UFs e
montar o desenho, sempre a frio (cache das UFs limpo antes); o `savefig` fica de fora, ele roda depois do título.

    uv run scripts/plots.py 3550308 3518800 431490 -o rmsp.svg   # ou: make plots CODS="3550308 3518800"
    uv run scripts/plots.py                                       # regera a galeria do README em docs/img/
"""

import argparse
import math
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from geoibge import desenho  # noqa: E402  (só stdlib: não carrega geopandas)

DESTINO = RAIZ / "docs" / "img"
DPI = 150  # do fundo rasterizado
# arquivo → (título, série)
GALERIA = {
    "plot_rmsp": ("Grande São Paulo e ABC",
                  ["3550308", "3518800", "3534401", "3547809", "3548708", "3513801", "3548807", "3529401"]),
    "plot_nordeste": ("Capitais do Nordeste",
                      ["2111300", "2211001", "2304400", "2408102", "2507507", "2611606", "2704302", "2800308",
                       "2927408"]),
    "plot_capitais": ("27 capitais",
                      ["1100205", "1200401", "1302603", "1400100", "1501402", "1600303", "1721000", "2111300",
                       "2211001", "2304400", "2408102", "2507507", "2611606", "2704302", "2800308", "2927408",
                       "3106200", "3205309", "3304557", "3550308", "4106902", "4205407", "4314902", "5002704",
                       "5103403", "5208707", "5300108"]),
}


def _area(anel) -> float:
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(anel, anel[1:])) / 2


def _path(geometria: dict, cosseno: float):
    """Path do matplotlib (lon × cosseno, lat); exterior anti-horário e buracos horários, para a regra nonzero."""
    from matplotlib.path import Path as MplPath

    poligonos = geometria["coordinates"] if geometria["type"] == "MultiPolygon" else [geometria["coordinates"]]
    vertices, codigos = [], []
    for poligono in poligonos:
        for i, anel in enumerate(poligono):
            pontos = [(lon * cosseno, lat) for lon, lat in anel]
            if (_area(pontos) > 0) != (i == 0):  # exterior (i = 0) positivo, buraco negativo
                pontos.reverse()
            vertices += pontos
            codigos += [MplPath.MOVETO] + [MplPath.LINETO] * (len(pontos) - 2) + [MplPath.CLOSEPOLY]
    return MplPath(vertices, codigos)


def agrupar(codigos) -> dict[str, list[str]]:
    """Códigos (6 ou 7 dígitos, repetidos ou não) → {cd_uf: [códigos de 7 dígitos]}, na ordem da série."""
    por_uf: dict[str, list[str]] = {}
    for codigo in codigos:
        cd_mun = desenho.resolver(codigo)
        if cd_mun not in por_uf.setdefault(cd_mun[:2], []):
            por_uf[cd_mun[:2]].append(cd_mun)
    return por_uf


def plotar(codigos, titulo: str | None = None, largura_pol: float = 6.0):
    """Figura do matplotlib com a série pintada; o título termina com o tempo de execução."""
    import matplotlib

    matplotlib.use("Agg")
    matplotlib.rcParams["svg.hashsalt"] = "geoibge"  # ids de clip-path fixos entre execuções
    import matplotlib.pyplot as plt
    from matplotlib.collections import PatchCollection
    from matplotlib.patches import PathPatch

    for cache in (desenho._uf, desenho._indice):  # a frio: o tempo não depende das séries anteriores
        cache.cache_clear()
    t0 = time.perf_counter()
    por_uf = agrupar(codigos)
    if not por_uf:
        raise ValueError("série vazia: informe ao menos um código IBGE")
    caixas = [desenho._uf(cd_uf)["bbox"] for cd_uf in por_uf]
    xmin, ymin = min(c[0] for c in caixas), min(c[1] for c in caixas)
    xmax, ymax = max(c[2] for c in caixas), max(c[3] for c in caixas)
    cosseno = math.cos(math.radians((ymin + ymax) / 2))  # equirretangular no paralelo central, como o svg()
    lado = max((xmax - xmin) * cosseno, ymax - ymin)
    cores = desenho.CORES

    fundo, agua, destaque, contornos, pequenos = [], [], [], [], []
    for cd_uf, serie in por_uf.items():
        pedidos = set(serie)
        for f in desenho._uf(cd_uf)["features"]:
            path = _path(f["geometry"], cosseno)
            nivel = f["properties"]["nivel"]
            if nivel == "uf":
                contornos.append(path)
            elif f["id"] in pedidos:
                destaque.append(path)
                (x0, y0), (x1, y1) = path.get_extents().get_points()
                if max(x1 - x0, y1 - y0) < lado * desenho.RAIO_MARCADOR / desenho.LADO_PX:
                    pequenos.append(((x0 + x1) / 2, (y0 + y1) / 2))
            else:
                (fundo if nivel == "municipio" else agua).append(path)

    fig, ax = plt.subplots(figsize=(largura_pol, largura_pol * (ymax - ymin) / ((xmax - xmin) * cosseno)))
    # fundo e água viram imagem dentro do SVG (milhares de municípios em vetor passam de 9 MB); a série e as
    # divisas das UFs seguem em vetor
    camadas = [(fundo, dict(facecolor=cores["fundo"], edgecolor=cores["borda"], linewidth=0.3, rasterized=True)),
               (agua, dict(facecolor=cores["agua"], edgecolor="none", rasterized=True)),
               (destaque, dict(facecolor=cores["destaque"], edgecolor=cores["destaque"], linewidth=0.3)),
               (contornos, dict(facecolor="none", edgecolor=cores["uf"], linewidth=0.8))]
    for paths, estilo in camadas:
        if paths:
            ax.add_collection(PatchCollection([PathPatch(p) for p in paths], **estilo))
    if pequenos:
        ax.scatter(*zip(*pequenos), s=120, facecolors="none", edgecolors=cores["destaque"], linewidths=1.2)
    ax.set_xlim(xmin * cosseno, xmax * cosseno)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal")
    ax.set_axis_off()

    n = sum(map(len, por_uf.values()))
    ms = (time.perf_counter() - t0) * 1000
    cabeca = titulo or f"{n} município{'s' if n > 1 else ''}"
    ax.set_title(f"{cabeca} · {len(por_uf)} UF{'s' if len(por_uf) > 1 else ''} · {fmt(ms)}", fontsize=10)
    fig.tight_layout()
    return fig, ms


def fmt(ms: float) -> str:
    return f"{ms:.1f} ms" if ms < 100 else f"{ms:.0f} ms"


def salvar(fig, destino: Path) -> Path:
    import matplotlib.pyplot as plt

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    # sem data e com hashsalt fixo: o SVG só muda quando o desenho (ou o tempo do título) muda
    fig.savefig(destino, format="svg", dpi=DPI, bbox_inches="tight", metadata={"Date": None})
    plt.close(fig)
    return destino


def main(argv: list[str] | None = None) -> int:
    from rich.console import Console
    from rich.table import Table

    parser = argparse.ArgumentParser(prog="plots.py", description=__doc__.splitlines()[0])
    parser.add_argument("codigos", nargs="*", help="códigos IBGE de 6 ou 7 dígitos; sem nenhum, regera a galeria")
    parser.add_argument("-o", "--saida", type=Path, help="SVG de saída (padrão: data/mapas/plot.svg)")
    parser.add_argument("-t", "--titulo", help="início do título (o tempo vem depois)")
    args = parser.parse_args(argv)
    if not args.codigos and (args.saida or args.titulo):
        parser.error("-o e -t pedem códigos; sem códigos, o script regera a galeria em docs/img/")
    console = Console(highlight=False)

    if args.codigos:
        pedidos = {(args.saida.resolve() if args.saida else RAIZ / "data" / "mapas" / "plot.svg"): (args.titulo, args.codigos)}
    else:
        pedidos = {DESTINO / f"{nome}.svg": item for nome, item in GALERIA.items()}

    tabela = Table(title="série de códigos IBGE → SVG do matplotlib")
    for coluna, justify in (("arquivo", "left"), ("municípios", "right"), ("UFs", "right"), ("tempo", "right")):
        tabela.add_column(coluna, justify=justify)
    for destino, (titulo, codigos) in pedidos.items():
        try:
            fig, ms = plotar(codigos, titulo)
        except ValueError as erro:
            console.print(f"[red]erro:[/] {erro}")
            return 2
        por_uf = agrupar(codigos)
        salvar(fig, destino)
        tabela.add_row(str(destino.relative_to(RAIZ) if destino.is_relative_to(RAIZ) else destino),
                       str(sum(map(len, por_uf.values()))), str(len(por_uf)), fmt(ms))
    console.print(tabela)
    return 0


if __name__ == "__main__":
    sys.exit(main())
