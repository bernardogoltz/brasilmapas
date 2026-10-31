import marimo

__generated_with = "0.25.2"

app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo
    from lonboard import Map, PolygonLayer, ScatterplotLayer

    import geoibge as gi

    return Map, PolygonLayer, ScatterplotLayer, gi, mo


@app.cell
def _(mo):
    mo.md("""
    # 05 · Explorador

    UF → municípios no mapa (lonboard); clique no mapa → `geoibge.reverse()` do ponto.
    Rodar como app: `make explorador`.
    """)
    return


@app.cell
def _(gi, mo):
    lista_ufs = gi.ufs(resolucao="baixa")
    uf = mo.ui.dropdown(lista_ufs.sg_uf.tolist(), value="SP", label="UF")
    resolucao = mo.ui.radio(["baixa", "media", "alta"], value="baixa", label="resolução", inline=True)
    mo.hstack([uf, resolucao])
    return resolucao, uf


@app.cell
def _(gi, resolucao, uf):
    municipios = gi.municipios(uf=uf.value, resolucao=resolucao.value)
    return (municipios,)


@app.cell
def _(Map, PolygonLayer, mo, municipios):
    camada = PolygonLayer.from_geopandas(
        municipios[["cd_mun", "nm_mun", "geometry"]],
        get_fill_color=[30, 120, 180, 60],
        get_line_color=[30, 60, 90, 200],
        line_width_min_pixels=0.5,
        pickable=True,
    )
    mapa = mo.ui.anywidget(Map(layers=[camada]))
    mapa
    return (mapa,)


@app.cell
def _(gi, mapa, mo):
    clique = mapa.value.get("clicked_point") if isinstance(mapa.value, dict) else None
    if clique:
        lon, lat = clique
        resposta = gi.reverse((lat, lon)).iloc[0].dropna().to_dict()
        saida = mo.ui.table([resposta])
    else:
        saida = mo.md("_Clique no mapa para o reverse()._")
    saida
    return


@app.cell
def _(gi, municipios, mo):
    relatorio = gi.validar(municipios)
    mo.vstack([
        mo.md(f"**{len(municipios)} municípios** · edição {municipios.attrs['edicao']} · "
              f"{(~relatorio.ok).sum()} com problema"),
        mo.ui.table(relatorio[~relatorio.ok] if (~relatorio.ok).any() else relatorio.head(10)),
    ])
    return


if __name__ == "__main__":
    app.run()
