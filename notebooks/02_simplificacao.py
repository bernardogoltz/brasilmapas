import marimo

__generated_with = "0.25.2"

app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import pandas as pd

    import geoibge as gi

    return gi, mo, pd


@app.cell
def _(mo):
    mo.md("""
    # 02 · Simplificação

    Tolerância × tamanho do GeoJSON × fidelidade, numa UF. Compara a simplificação ingênua
    (`ST_SimplifyPreserveTopology` município a município) com a de cobertura (`ST_CoverageSimplify`):
    só a segunda mantém as divisas sem fresta. Calibra `tolerancia_media` e `tolerancia_baixa` do dbt.
    """)
    return


@app.cell
def _(mo):
    UFS = "AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO".split()
    uf = mo.ui.dropdown(UFS, value="RJ", label="UF")
    tolerancia = mo.ui.slider(steps=[0.0001, 0.0005, 0.001, 0.002, 0.005, 0.01, 0.02], value=0.001, label="tolerância (graus)")
    mo.hstack([uf, tolerancia])
    return tolerancia, uf


@app.cell
def _(gi, pd, tolerancia, uf):
    SQL = """
    with m as (
        select cd_mun, geom_alta as geom from marts.geo_municipio
        where edicao = (select edicao from meta.publicacao) and sg_uf = %(uf)s
    ), s as (
        select geom, unnest(array['original', 'ingenua', 'cobertura']) as metodo,
               unnest(array[geom, st_simplifypreservetopology(geom, %(tol)s),
                            st_coveragesimplify(geom, %(tol)s) over ()]) as g
        from m
    )
    select metodo,
           round(sum(octet_length(st_asgeojson(g, 5))) / 1024.0, 1) as geojson_kb,
           sum(st_npoints(g)) as vertices,
           round((max(st_hausdorffdistance(geom, g)) * 111)::numeric, 3) as hausdorff_max_km,
           (select count(*) from (select st_coverageinvalidedges(s2.g) over () as e from s s2 where s2.metodo = s.metodo) x
            where e is not null) as arestas_invalidas
    from s group by metodo order by geojson_kb desc
    """
    with gi.conectar().cursor() as cur:
        cur.execute(SQL, {"uf": uf.value, "tol": tolerancia.value})
        comparacao = pd.DataFrame(cur.fetchall(), columns=[c.name for c in cur.description])
    comparacao
    return


@app.cell
def _(mo):
    mo.md("""
    Leitura: `arestas_invalidas` > 0 na ingênua são as frestas entre vizinhos; a de cobertura fica igual à original.
    """)
    return


if __name__ == "__main__":
    app.run()
