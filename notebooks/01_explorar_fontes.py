import marimo

__generated_with = "0.25.2"

app = marimo.App(width="medium")


@app.cell
def _():
    import hashlib
    import urllib.request
    from pathlib import Path

    import geopandas as gpd
    import marimo as mo
    import pyogrio
    import shapely

    return Path, gpd, hashlib, mo, pyogrio, shapely, urllib


@app.cell
def _(mo):
    mo.md("""
    # 01 · Explorar fontes

    Malha municipal 2025 de uma UF, lida do zip com pyogrio (`/vsizip/`).
    """)
    return


@app.cell
def _(mo):
    UFS = "AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO".split()
    uf = mo.ui.dropdown(UFS, value="SP", label="UF")
    uf
    return (uf,)


@app.cell
def _(Path, hashlib, uf, urllib):
    EDICAO = 2025
    GEOFTP = "https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais"
    url = f"{GEOFTP}/malhas_municipais/municipio_{EDICAO}/UFs/{uf.value}/{uf.value}_Municipios_{EDICAO}.zip"
    zip_path = Path(__file__).parent.parent / f"data/raw/malha_municipal/{EDICAO}/{uf.value}_Municipios_{EDICAO}.zip"
    if not zip_path.exists():
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(url, zip_path)
    sha256 = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    return sha256, url, zip_path


@app.cell
def _(mo, pyogrio, sha256, url, zip_path):
    info = pyogrio.read_info(f"/vsizip/{zip_path}")
    mo.md(f"""
    - **url:** `{url}`
    - **bytes:** {zip_path.stat().st_size:,} · **sha256:** `{sha256[:16]}…`
    - **CRS:** `{info["crs"]}` · **geometria:** {info["geometry_type"]} · **feições:** {info["features"]}
    - **colunas:** {", ".join(f"`{c}` ({t})" for c, t in zip(info["fields"], info["dtypes"]))}
    """)
    return


@app.cell
def _(gpd, shapely, zip_path):
    gdf = gpd.read_file(f"/vsizip/{zip_path}", engine="pyogrio")
    gdf["vertices"] = shapely.get_num_coordinates(gdf.geometry.values)
    gdf["valida"] = gdf.geometry.is_valid
    gdf.drop(columns="geometry").sort_values("vertices", ascending=False)
    return (gdf,)


@app.cell
def _(gdf, mo):
    mo.md(f"""
    - **vértices:** total {gdf["vertices"].sum():,} · mediana {gdf["vertices"].median():,.0f} · máx {gdf["vertices"].max():,}
    - **inválidas:** {(~gdf["valida"]).sum()}
    - **códigos duplicados:** {gdf["CD_MUN"].duplicated().sum()}
    """)
    return


@app.cell
def _(gdf):
    import warnings

    from lonboard import Map, PolygonLayer

    warnings.filterwarnings("ignore", message="Input being reprojected")

    Map(PolygonLayer.from_geopandas(gdf[["CD_MUN", "NM_MUN", "geometry"]], get_fill_color=[30, 120, 180, 80], get_line_color=[30, 60, 90], line_width_min_pixels=0.5))
    return


if __name__ == "__main__":
    app.run()
