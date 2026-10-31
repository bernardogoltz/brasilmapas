import zipfile

import geopandas as gpd
import pytest
from shapely.geometry import box

from ibge import validar


def zip_shp(tmp_path, n, crs="EPSG:4674", nome="BR_Municipios_2099"):
    gdf = gpd.GeoDataFrame({"CD_MUN": [str(i) for i in range(n)]}, geometry=[box(i, 0, i + 1, 1) for i in range(n)], crs=crs)
    shp = tmp_path / f"{nome}.shp"
    gdf.to_file(shp)
    z = tmp_path / f"{nome}.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for f in tmp_path.glob(f"{nome}.*"):
            if f.suffix != ".zip":
                zf.write(f, f.name)
    return z


def test_validar_zip_ok(tmp_path):
    res = validar.validar_zip(zip_shp(tmp_path, 5), feicoes=(1, 10))
    assert res["camada"] == "BR_Municipios_2099" and res["feicoes"] == 5 and "CD_MUN" in res["colunas"]


def test_validar_zip_contagem_fora(tmp_path):
    with pytest.raises(validar.ValidacaoError, match="feições"):
        validar.validar_zip(zip_shp(tmp_path, 3), feicoes=(5, 10))


def test_validar_zip_crs_errado(tmp_path):
    with pytest.raises(validar.ValidacaoError, match="CRS"):
        validar.validar_zip(zip_shp(tmp_path, 3, crs="EPSG:4326"), feicoes=(1, 10))


def test_camada_municipios():
    assert validar.camada_municipios(["x"]) == "x"
    assert validar.camada_municipios(["BRUFE250GC_SIR", "BRMUE250GC_SIR"]) == "BRMUE250GC_SIR"
    with pytest.raises(validar.ValidacaoError):
        validar.camada_municipios(["a", "b"])
