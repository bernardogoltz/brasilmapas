"""geoibge.desenho: UF com município em destaque a partir dos GeoJSON publicados (sem banco, sem rede)."""

import html
import io
import json
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

import geoibge as gi
from geoibge import desenho
from geoibge.cli import main

SVG = "{http://www.w3.org/2000/svg}"


def test_import_nao_carrega_geopandas():
    codigo = "import sys, geoibge; geoibge.svg(3550308); print('geopandas' in sys.modules, 'psycopg' in sys.modules)"
    saida = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, check=True).stdout
    assert saida.split() == ["False", "False"]


def test_mapas_publicados_cobrem_o_brasil():
    arquivos = sorted(desenho.DIR.glob("*.json"))
    assert len(arquivos) == 27
    municipios = 0
    for arquivo in arquivos:
        fc = json.loads(arquivo.read_bytes())
        uf, *resto = fc["features"]
        assert fc["type"] == "FeatureCollection" and arquivo.stem == fc["cd_uf"] == uf["id"]
        assert uf["properties"]["nivel"] == "uf" and len(fc["bbox"]) == 4
        assert all(f["id"].startswith(fc["cd_uf"]) and len(f["id"]) == 7 for f in resto)
        assert all(f["geometry"]["type"] == "MultiPolygon" for f in fc["features"])
        municipios += sum(f["properties"]["nivel"] == "municipio" for f in resto)
    assert municipios >= 5570


def test_mapa_destaca_so_o_pedido():
    fc = gi.mapa(3550308)
    assert fc["sg_uf"] == "SP" and fc["destaque"] == "3550308"
    marcados = [f["id"] for f in fc["features"] if f["properties"]["destaque"]]
    assert marcados == ["3550308"]
    assert "destaque" not in desenho._uf("35")["features"][1]["properties"]  # cache intacto


@pytest.mark.parametrize("entrada", ["355030", " 3550308 ", 3550308])
def test_resolver_aceita_6_e_7_digitos(entrada):
    assert desenho.resolver(entrada) == "3550308"


@pytest.mark.parametrize("entrada, erro", [
    ("12345", "inválido"), ("abc", "inválido"), ("9912345", "UF 99"), ("3599999", "inexistente"),
])
def test_resolver_erros(entrada, erro):
    with pytest.raises(ValueError, match=erro):
        desenho.resolver(entrada)


def test_resolver_exige_um_so_criterio():
    for args in ({}, {"municipio": 3550308, "cep": "01310100"}):
        with pytest.raises(ValueError, match="um dos dois"):
            desenho.resolver(**args)


def _viacep(monkeypatch, resposta: dict):
    pedidos = []

    def urlopen(req, timeout):
        pedidos.append(req.full_url)
        return io.BytesIO(json.dumps(resposta).encode())

    desenho.cep_para_municipio.cache_clear()
    monkeypatch.setattr(desenho.urllib.request, "urlopen", urlopen)
    return pedidos


def test_cep_via_viacep(monkeypatch):
    pedidos = _viacep(monkeypatch, {"cep": "01310-100", "ibge": "3550308"})
    assert gi.mapa(cep="01310-100")["destaque"] == "3550308"
    assert pedidos == ["https://viacep.com.br/ws/01310100/json/"]


def test_cep_inexistente_e_invalido(monkeypatch):
    pedidos = _viacep(monkeypatch, {"erro": "true"})
    with pytest.raises(ValueError, match="CEP inexistente"):
        desenho.cep_para_municipio("99999-999")
    with pytest.raises(ValueError, match="CEP inválido"):
        desenho.cep_para_municipio("123")
    assert len(pedidos) == 1  # o inválido nem vai à rede


def _svg(codigo) -> ET.Element:
    return ET.fromstring(gi.svg(codigo, largura=400))


def test_svg_valido_com_destaque():
    raiz = _svg("3550308")
    assert raiz.get("width") == "400" and raiz.find(f"{SVG}title").text == "São Paulo (SP)"
    destaque = raiz.find(f"{SVG}path[@id='m3550308']")
    assert destaque is not None and destaque.get("d").startswith("M")
    assert raiz.find(f"{SVG}circle") is None  # São Paulo é visível sem marcador


def test_svg_marca_municipio_pequeno():
    assert _svg("3500600").find(f"{SVG}circle") is not None  # Águas de São Pedro


def test_svg_cabe_marcador_na_borda():
    raiz = _svg("2605459")  # Fernando de Noronha, na ponta direita de PE
    x0, y0, w, h = map(float, raiz.get("viewBox").split())
    c = raiz.find(f"{SVG}circle")
    r = float(c.get("r"))
    assert x0 <= float(c.get("cx")) - r and float(c.get("cx")) + r <= x0 + w


def test_svg_lagoa_e_df():
    assert _svg("4300002").find(f"{SVG}path[@id='m4300002']") is not None  # área operacional também se destaca
    assert _svg("5300108").find(f"{SVG}path[@id='m5300108']") is not None


def test_vitoria_sem_trindade():
    es = desenho._uf("32")
    assert es["partes_omitidas"] == ["3205309"]
    assert es["bbox"][2] < -39  # Trindade fica em -29°
    assert desenho._uf("26")["bbox"][2] > -33  # Fernando de Noronha fica


@pytest.mark.parametrize("caixa, esperado", [
    ((-53.1, -25.3, -44.2, -19.8), (0.008263, 3)),  # SP
    ((-48.3, -16.05, -47.3, -15.5), (0.000962, 4)),  # DF
])
def test_parametros_por_escala(caixa, esperado):
    tolerancia, decimais = desenho.parametros(*caixa)
    assert tolerancia == pytest.approx(esperado[0], rel=0.01) and decimais == esperado[1]


def test_montar_feature_collection():
    quadrado = '{"type":"MultiPolygon","coordinates":[[[[0,0],[2,0],[2,1],[0,1],[0,0]]]]}'
    uf = {"cd_uf": "99", "sg_uf": "XX", "nm_uf": "Teste", "partes_omitidas": []}
    linhas = [
        {"id": None, "nome": None, "is_municipio": None, "geometria": quadrado, "ponto": None},
        {"id": "9900001", "nome": "A", "is_municipio": True, "geometria": quadrado,
         "ponto": '{"type":"Point","coordinates":[1,0.5]}'},
        {"id": "9900002", "nome": "Lagoa", "is_municipio": False, "geometria": quadrado,
         "ponto": '{"type":"Point","coordinates":[1,0.5]}'},
    ]
    fc = desenho.montar(uf, linhas, 2025, 0.01)
    assert fc["bbox"] == [0, 0, 2, 1] and fc["edicao"] == 2025
    assert [f["properties"]["nivel"] for f in fc["features"]] == ["uf", "municipio", "area_operacional"]
    assert fc["features"][1]["properties"]["ponto"] == [1, 0.5]


def test_sql_exportacao_simplifica_cobertura_por_uf():
    assert "st_coveragesimplify(geom, %(tolerancia)s) over ()" in desenho.SQL_GEOMETRIAS
    assert "st_coverageunion" in desenho.SQL_GEOMETRIAS and "%(remota)s" in desenho.SQL_EXTENSAO


def test_cli_mapa(tmp_path, capsys):
    assert main(["mapa", "3550308", "-o", str(tmp_path / "sp.svg")]) == 0
    assert (tmp_path / "sp.svg").read_text().startswith("<svg")
    assert main(["mapa", "330455", "-o", str(tmp_path / "rj.geojson")]) == 0
    assert json.loads((tmp_path / "rj.geojson").read_text())["destaque"] == "3304557"
    assert main(["mapa", "123"]) == 2 and "inválido" in capsys.readouterr().err


def _banco_disponivel() -> bool:
    try:
        gi.conectar().execute("select 1 from marts.geo_uf limit 1")
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _banco_disponivel(), reason="PostGIS local com marts indisponível")
def test_exportar_uma_uf(tmp_path):
    (caminho,) = desenho.exportar(tmp_path, ufs=["53"])
    fc = json.loads(caminho.read_bytes())
    assert caminho.name == "53.json" and [f["id"] for f in fc["features"]] == ["53", "5300108"]


# ---------------------------------------------------------------- data/mapas.json (uso externo)


def _svg_do_json(cat: dict, codigo: str, largura: int = 600) -> str:
    """Segue `cat["receita"]` ao pé da letra, sem o geoibge: é o que um usuário externo faria."""
    uf = cat["ufs"][codigo[:2]]
    mun = uf["municipios"][codigo]
    cores, raio = cat["cores"], cat["raio_marcador"]
    m, w, h = raio + 4, uf["largura"], uf["altura"]
    estilo = 'stroke-linejoin="round" vector-effect="non-scaling-stroke"'
    fundo = "".join(x["d"] for x in uf["municipios"].values() if x["nivel"] == "municipio")
    agua = "".join(x["d"] for x in uf["municipios"].values() if x["nivel"] == "area_operacional")
    partes = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-m} {-m} {w + 2 * m:.1f} {h + 2 * m:.1f}" '
        f'width="{largura}" height="{round(largura * (h + 2 * m) / (w + 2 * m))}">',
        f"<title>{html.escape(mun['nome'])} ({uf['sigla']})</title>",
        f'<path d="{fundo}" fill="{cores["fundo"]}" fill-rule="evenodd" stroke="{cores["borda"]}" '
        f'stroke-width="0.5" {estilo}/>',
    ]
    if agua:
        partes.append(f'<path d="{agua}" fill="{cores["agua"]}" fill-rule="evenodd" stroke="none"/>')
    partes += [
        f'<path id="m{codigo}" d="{mun["d"]}" fill="{cores["destaque"]}" fill-rule="evenodd" '
        f'stroke="{cores["destaque"]}" stroke-width="0.5" {estilo}/>',
        f'<path d="{uf["contorno"]}" fill="none" stroke="{cores["uf"]}" stroke-width="1.2" {estilo}/>',
    ]
    x0, y0, x1, y1 = mun["caixa"]
    if max(x1 - x0, y1 - y0) < raio:
        partes.append(f'<circle cx="{(x0 + x1) / 2:.1f}" cy="{(y0 + y1) / 2:.1f}" r="{raio}" fill="none" '
                      f'stroke="{cores["destaque"]}" stroke-width="2" {estilo}/>')
    partes.append("</svg>")
    return "\n".join(partes)


@pytest.fixture(scope="module")
def publicado() -> dict:
    return json.loads(desenho.JSON_PUBLICO.read_bytes())


def test_json_publicado_em_dia(publicado):
    assert publicado == json.loads(json.dumps(desenho.catalogo(), ensure_ascii=False))  # senão: make mapas-json
    assert len(publicado["ufs"]) == 27 and publicado["formato"] == "geoibge-mapas/1"
    assert sum(len(u["municipios"]) for u in publicado["ufs"].values()) >= 5570


@pytest.mark.parametrize("codigo", ["3550308", "3500600", "2605459", "4300002", "5300108", "3205309"])
def test_json_reproduz_o_svg(publicado, codigo):
    assert _svg_do_json(publicado, codigo) == gi.svg(codigo)


def test_cli_exportar_json(tmp_path):
    destino = tmp_path / "sub" / "mapas.json"
    assert main(["exportar-json", "--destino", str(destino)]) == 0
    cat = json.loads(destino.read_bytes())
    assert cat["ufs"]["53"]["municipios"]["5300108"]["nome"] == "Brasília"
    assert set(cat["cores"]) == {"fundo", "agua", "borda", "uf", "destaque"}


def test_data_mapas_json_versionado():
    raiz = desenho.JSON_PUBLICO.parents[1]
    ignorado = subprocess.run(["git", "check-ignore", "-q", str(desenho.JSON_PUBLICO)], cwd=raiz).returncode
    assert ignorado == 1  # 1 = não ignorado; o resto de data/ (shapefiles) continua fora
    assert subprocess.run(["git", "check-ignore", "-q", "data/BR_UF_2025"], cwd=raiz).returncode == 0
