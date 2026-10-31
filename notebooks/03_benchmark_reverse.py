import marimo

__generated_with = "0.25.2"

app = marimo.App(width="medium")


@app.cell
def _():
    import time

    import marimo as mo
    import numpy as np
    import pandas as pd

    import geoibge as gi

    return gi, mo, np, pd, time


@app.cell
def _(mo):
    mo.md("""
    # 03 · Benchmark do reverse()

    Pontos aleatórios no bbox do Brasil. Compara o polígono inteiro (`geo_municipio.geom_alta`)
    com os pedaços do `ST_Subdivide` (`lkp_municipio`) e mede as metas do README:
    p95 < 50 ms por ponto e 100 mil pontos em < 60 s.
    """)
    return


@app.cell
def _(mo):
    n_lote = mo.ui.slider(steps=[1_000, 10_000, 100_000], value=100_000, label="pontos no lote")
    n_lote
    return (n_lote,)


@app.cell
def _(np, pd):
    rng = np.random.default_rng(42)

    def pontos(n):
        return pd.DataFrame({"lat": rng.uniform(-33.7, 5.3, n), "lon": rng.uniform(-73.9, -34.8, n)})

    return (pontos,)


@app.cell
def _(gi, np, pd, pontos, time):
    TABELAS = {
        "inteiro": "select cd_mun from marts.geo_municipio where edicao = %(e)s and st_intersects(geom_alta, st_setsrid(st_makepoint(%(lon)s, %(lat)s), 4674)) limit 1",
        "subdividido": "select cd_mun from marts.lkp_municipio where edicao = %(e)s and st_intersects(geom, st_setsrid(st_makepoint(%(lon)s, %(lat)s), 4674)) limit 1",
    }
    edicao = int(gi.edicoes().query("publicada").edicao.iloc[0])
    amostra = pontos(300)
    latencias = {}
    with gi.conectar().cursor() as cur:
        for nome, sql in TABELAS.items():
            ms = []
            for p in amostra.itertuples():
                _t0 = time.perf_counter()
                cur.execute(sql, {"e": edicao, "lat": p.lat, "lon": p.lon})
                cur.fetchall()
                ms.append((time.perf_counter() - _t0) * 1000)
            latencias[nome] = ms
    por_ponto = pd.DataFrame({k: np.percentile(v, [50, 95, 99]) for k, v in latencias.items()}, index=["p50_ms", "p95_ms", "p99_ms"]).round(2)
    por_ponto
    return


@app.cell
def _(gi, n_lote, pontos, time):
    lote = pontos(n_lote.value)
    t0 = time.perf_counter()
    resultado = gi.reverse(lote)
    segundos = time.perf_counter() - t0
    resumo = {
        "pontos": len(lote),
        "segundos": round(segundos, 2),
        "pontos_por_s": round(len(lote) / segundos),
        "% dentro do Brasil": round(resultado.cd_mun.notna().mean() * 100, 1),
    }
    resumo
    return


if __name__ == "__main__":
    app.run()
