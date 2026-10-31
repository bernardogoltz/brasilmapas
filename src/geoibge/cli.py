"""CLI fina: `geoibge validar SP RJ 3550308`, `geoibge reverse -23.55 -46.63`, `geoibge edicoes`."""

import argparse

import pandas as pd

import geoibge as gi
from geoibge.core import normalizar_uf


def separar(ids: list[str]) -> tuple[list[str], list[str]]:
    """Divide a lista em UFs (sigla ou código de 2 dígitos) e municípios."""
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
    v.add_argument("--resolucao", default="media", choices=gi.core.RESOLUCOES)
    r = sub.add_parser("reverse", help="município de um ponto")
    r.add_argument("lat", type=float)
    r.add_argument("lon", type=float)
    sub.add_parser("edicoes", help="edições carregadas")
    args = parser.parse_args(argv)

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
