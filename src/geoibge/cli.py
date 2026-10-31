"""CLI fina: `geoibge validar SP RJ 3550308`, `geoibge reverse -23.55 -46.63`, `geoibge mapa 3550308`, `geoibge edicoes`.

Imports pesados (pandas, geopandas, psycopg) só nos comandos que usam o banco.
"""

import argparse
import json
import sys
from pathlib import Path

import geoibge as gi


def separar(ids: list[str]) -> tuple[list[str], list[str]]:
    """Divide a lista em UFs (sigla ou código de 2 dígitos) e municípios."""
    from geoibge.core import normalizar_uf

    ufs, municipios = [], []
    for item in ids:
        try:
            normalizar_uf(item)
            ufs.append(item)
        except ValueError:
            municipios.append(item)
    return ufs, municipios


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="geoibge")
    parser.add_argument("--edicao", type=int)
    sub = parser.add_subparsers(dest="comando", required=True)
    v = sub.add_parser("validar", help="valida UFs e municípios")
    v.add_argument("ids", nargs="+")
    v.add_argument("--resolucao", default="media", choices=("alta", "media", "baixa"))
    r = sub.add_parser("reverse", help="município de um ponto")
    r.add_argument("lat", type=float)
    r.add_argument("lon", type=float)
    sub.add_parser("edicoes", help="edições carregadas")
    m = sub.add_parser("mapa", help="desenho da UF com o município em destaque (SVG ou GeoJSON; sem banco)")
    m.add_argument("municipio", nargs="?", help="código IBGE de 6 ou 7 dígitos")
    m.add_argument("--cep", help="CEP no lugar do código (consulta a ViaCEP)")
    m.add_argument("-o", "--saida", type=Path, help=".svg, .json ou .geojson; sem -o, SVG na saída padrão")
    m.add_argument("--largura", type=int, default=600)
    e = sub.add_parser("exportar-mapas", help="gera os GeoJSON por UF a partir dos marts")
    e.add_argument("--destino", type=Path, default=gi.desenho.DIR)
    j = sub.add_parser("exportar-json", help="grava data/mapas.json: paths projetados de todas as UFs (sem banco)")
    j.add_argument("--destino", type=Path, default=gi.desenho.JSON_PUBLICO)
    args = parser.parse_args(argv)

    if args.comando == "mapa":
        try:
            if args.saida and args.saida.suffix in (".json", ".geojson"):
                texto = json.dumps(gi.mapa(args.municipio, cep=args.cep), ensure_ascii=False, separators=(",", ":"))
            else:
                texto = gi.svg(args.municipio, cep=args.cep, largura=args.largura)
        except ValueError as erro:
            print(f"erro: {erro}", file=sys.stderr)
            return 2
        if args.saida:
            args.saida.parent.mkdir(parents=True, exist_ok=True)
            args.saida.write_text(texto, encoding="utf-8")
            print(args.saida)
        else:
            print(texto)
        return 0
    if args.comando == "exportar-json":
        print(gi.desenho.exportar_json(args.destino))
        return 0
    if args.comando == "exportar-mapas":
        for caminho in gi.desenho.exportar(args.destino, edicao=args.edicao):
            print(caminho)
        return 0

    import pandas as pd

    pd.set_option("display.width", 200)
    if args.comando == "validar":
        ufs, municipios = separar(args.ids)
        partes = []
        if ufs:
            partes.append(gi.validar(gi.ufs(ufs, resolucao=args.resolucao, edicao=args.edicao)))
        if municipios:
            partes.append(gi.validar(gi.municipios(municipios, resolucao=args.resolucao, edicao=args.edicao)))
        rel = pd.concat(partes, ignore_index=True)
        print(rel.to_string(index=False))
        return 0 if rel.ok.all() else 1
    if args.comando == "reverse":
        print(gi.reverse((args.lat, args.lon), edicao=args.edicao).T.to_string(header=False))
        return 0
    print(gi.edicoes().to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
