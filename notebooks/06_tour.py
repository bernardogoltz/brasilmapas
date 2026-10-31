import marimo

__generated_with = "0.25.2"

app = marimo.App(width="medium")


@app.cell
def _():
    import geopandas as gpd
    import marimo as mo
    import pandas as pd
    from lonboard import Map, PolygonLayer, ScatterplotLayer

    import geoibge as gi

    return Map, PolygonLayer, ScatterplotLayer, gi, gpd, mo, pd


@app.cell
def _(mo):
    mo.md("""
    # 06 · Tour

    Do dado ao mapa, só com a biblioteca `geoibge`: a origem (edições e cargas), as três perguntas
    do projeto (municípios, estados, ponto → hierarquia), a validação e onde acompanhar o pipeline.
    Rodar: `make tour` (requer `make up` e as cargas feitas).
    """)
    return


@app.cell
def _(gi, mo):
    lista_edicoes = gi.edicoes()
    cargas = gi.core._consulta("""
        select fonte, edicao, feicoes, pg_size_pretty(bytes) as tamanho, duracao_s, carregado_em
        from meta.cargas c
        where carregado_em = (select max(carregado_em) from meta.cargas where fonte = c.fonte)
        order by fonte
    """)
    mo.vstack([
        mo.md("## 1 · De onde vem o dado\n\nEdições carregadas (a publicada é a padrão) e a última carga de cada fonte."),
        mo.ui.table(lista_edicoes, selection=None),
        mo.ui.table(cargas, selection=None),
    ])
    return


@app.cell
def _(mo):
    mo.md("""
    ## 2 · Mostre estes estados

    `ufs()` aceita sigla ou código; a resolução escolhe a geometria simplificada no banco.
    """)
    return


@app.cell
def _(mo):
    escolha_ufs = mo.ui.multiselect(
        "AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO".split(),
        value=["SP", "RJ", "MG", "ES"], label="UFs",
    )
    resolucao = mo.ui.radio(["baixa", "media", "alta"], value="baixa", label="resolução", inline=True)
    mo.hstack([escolha_ufs, resolucao], justify="start")
    return escolha_ufs, resolucao


@app.cell
def _(escolha_ufs, gi, resolucao):
    estados = gi.ufs(escolha_ufs.value or None, resolucao=resolucao.value)
    estados.drop(columns="geometry")
    return (estados,)


@app.cell
def _(mo):
    mo.md("""
    ## 3 · Mostre estes municípios

    Código de 7 dígitos, de 6 (sem o verificador) ou `(nome, UF)`, misturados na mesma lista.
    """)
    return


@app.cell
def _(gi, resolucao):
    cidades = gi.municipios(["3550308", "330455", ("Belo Horizonte", "MG"), ("Vitória", "ES")], resolucao=resolucao.value)
    cidades.drop(columns="geometry")
    return (cidades,)


@app.cell
def _(mo):
    mo.md("""
    ## 4 · Onde fica este ponto?

    Um lote de pontos numa ida ao banco: UF, município, regiões e, com o Censo 2022 carregado,
    distrito, subdistrito, bairro e setor. Pontos inválidos ou fora do Brasil voltam com `erro`.
    """)
    return


@app.cell
def _(gi, pd):
    pontos = pd.DataFrame({
        "local": ["Praça da Sé", "Cristo Redentor", "Praça da Liberdade", "Terceira Ponte", "Atlântico", "inválido"],
        "lat": [-23.5503, -22.9519, -19.9320, -20.3036, -21.0, 95.0],
        "lon": [-46.6340, -43.2105, -43.9380, -40.2925, -38.0, 0.0],
    })
    respostas = gi.reverse(pontos)
    colunas = [c for c in ["sg_uf", "nm_mun", "nm_rgi", "nm_dist", "nm_bairro", "cd_setor", "situacao", "erro", "aviso"] if c in respostas]
    pontos[["local"]].join(respostas[["lat", "lon", *colunas]])
    return pontos, respostas


@app.cell
def _(Map, PolygonLayer, ScatterplotLayer, cidades, estados, gpd, mo, pontos, respostas):
    achados = pontos[respostas.erro.isna()]
    camadas = [
        PolygonLayer.from_geopandas(estados[["sg_uf", "geometry"]], get_fill_color=[30, 120, 180, 30],
                                    get_line_color=[30, 60, 90, 220], line_width_min_pixels=1),
        PolygonLayer.from_geopandas(cidades[["cd_mun", "nm_mun", "geometry"]], get_fill_color=[230, 120, 30, 120],
                                    get_line_color=[160, 70, 10, 255], line_width_min_pixels=1, pickable=True),
    ]
    if len(achados):
        pts = gpd.GeoDataFrame(achados, geometry=gpd.points_from_xy(achados.lon, achados.lat), crs=estados.crs)
        camadas.append(ScatterplotLayer.from_geopandas(pts, get_fill_color=[200, 30, 60, 255], radius_min_pixels=5))
    mo.vstack([mo.md("**Mapa:** UFs escolhidas, os quatro municípios e os pontos resolvidos."), Map(layers=camadas)])
    return


@app.cell
def _(cidades, estados, gi, mo):
    rel_mun, rel_uf = gi.validar(cidades), gi.validar(estados)
    mo.vstack([
        mo.md(f"""
    ## 5 · Validação

    Calculada no banco pelas chaves (sem enviar geometria): validade, SRID e área contra o IBGE.
    **{int(rel_mun.ok.sum())}/{len(rel_mun)}** municípios e **{int(rel_uf.ok.sum())}/{len(rel_uf)}** UFs ok.
    """),
        mo.ui.table(rel_mun, selection=None),
    ])
    return


@app.cell
def _(mo):
    mo.md("""
    ## 6 · Acompanhar o pipeline

    `make obs` sobe Prometheus, exporters e Grafana (sem login), com três dashboards provisionados de `infra/grafana/`:

    | Dashboard | O que mostra |
    |---|---|
    | [geo · Pipeline](http://localhost:3000/d/geo-pipeline) | edição publicada, DAG runs e tasks (StatsD do Airflow), últimas cargas |
    | [geo · Qualidade](http://localhost:3000/d/geo-qualidade) | municípios por edição, divergência setores 2022 × malha, geometrias inválidas |
    | [geo · Banco](http://localhost:3000/d/geo-banco) | conexões, cache hit, consultas mais caras e as da `geoibge` (`pg_stat_statements`) |

    As consultas deste notebook aparecem no painel "Consultas da biblioteca geoibge".
    """)
    return


if __name__ == "__main__":
    app.run()
