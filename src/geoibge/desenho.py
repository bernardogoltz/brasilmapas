"""Desenho da UF com um município em destaque, a partir de GeoJSON estático (sem banco).

`exportar()` gera `mapas/{cd_uf}.json` a partir dos marts, uma vez por edição. `mapa()` e `svg()` só leem esses
arquivos, com cache por UF: o código IBGE já diz a UF (2 primeiros dígitos), então cada chamada abre um arquivo.
`exportar_json()` grava `data/mapas.json`: os paths já projetados de todas as UFs, para quem não usa Python.
Só stdlib aqui: `import geoibge.desenho` não carrega geopandas nem psycopg.
"""

import html
import json
import math
import re
import urllib.request
from functools import lru_cache
from pathlib import Path

DIR = Path(__file__).parent / "mapas"
LADO_PX = 1000  # simplificação por UF: erro de ~1 px num desenho de 1000 px no lado maior
DISTANCIA_REMOTA = 2.0  # graus; parte de município mais longe do continente sai (Trindade, de Vitória)
JSON_PUBLICO = Path(__file__).parents[2] / "data" / "mapas.json"
VIACEP = "https://viacep.com.br/ws/{cep}/json/"
RAIO_MARCADOR = 18  # unidades do viewBox (lado maior = LADO_PX); só para município pequeno demais para ver
CORES = {"fundo": "#e4e4e4", "agua": "#cfe1f2", "borda": "#ffffff", "uf": "#4d4d4d", "destaque": "#d62728"}


# ---------------------------------------------------------------- entrada


@lru_cache(maxsize=4096)
def cep_para_municipio(cep, timeout: float = 5.0) -> str:
    """CEP → código IBGE do município (7 dígitos), pela ViaCEP; precisa de rede."""
    digitos = re.sub(r"\D", "", str(cep))
    if len(digitos) != 8:
        raise ValueError(f"CEP inválido: {cep!r} (8 dígitos)")
    req = urllib.request.Request(VIACEP.format(cep=digitos), headers={"User-Agent": "geoibge"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        dado = json.load(resp)
    if dado.get("erro") or not dado.get("ibge"):
        raise ValueError(f"CEP inexistente: {cep!r}")
    return dado["ibge"]


@lru_cache(maxsize=None)
def _uf(cd_uf: str) -> dict:
    caminho = DIR / f"{cd_uf}.json"
    if not caminho.exists():
        raise ValueError(f"UF {cd_uf} sem mapa em {DIR} (rode `make mapas`)")
    return json.loads(caminho.read_bytes())


@lru_cache(maxsize=None)
def _indice(cd_uf: str) -> dict[str, int]:
    """Código de 7 e de 6 dígitos → posição da feição no arquivo da UF."""
    indice = {}
    for i, f in enumerate(_uf(cd_uf)["features"]):
        if f["properties"]["nivel"] != "uf":
            indice[f["id"]] = indice[f["id"][:6]] = i
    return indice


def resolver(municipio=None, cep=None) -> str:
    """Código IBGE (6 ou 7 dígitos) ou CEP → código de 7 dígitos presente nos mapas."""
    if (municipio is None) == (cep is None):
        raise ValueError("informe o município ou o CEP (um dos dois)")
    codigo = cep_para_municipio(cep) if cep is not None else str(municipio).strip()
    if not re.fullmatch(r"\d{6,7}", codigo):
        raise ValueError(f"município inválido: {codigo!r} (código IBGE de 6 ou 7 dígitos)")
    cd_uf = codigo[:2]
    if not (DIR / f"{cd_uf}.json").exists():
        raise ValueError(f"município inválido: {codigo} (UF {cd_uf} inexistente)")
    pos = _indice(cd_uf).get(codigo)
    if pos is None:
        raise ValueError(f"município {codigo} inexistente na edição {_uf(cd_uf)['edicao']}")
    return _uf(cd_uf)["features"][pos]["id"]


# ---------------------------------------------------------------- saída


def mapa(municipio=None, *, cep=None) -> dict:
    """GeoJSON (FeatureCollection) da UF: contorno, municípios e `destaque: true` no pedido."""
    cd_mun = resolver(municipio, cep)
    base = _uf(cd_mun[:2])
    features = [{**f, "properties": {**f["properties"], "destaque": f["id"] == cd_mun}} for f in base["features"]]
    return {**base, "destaque": cd_mun, "features": features}


def _aneis(geometria: dict):
    poligonos = geometria["coordinates"] if geometria["type"] == "MultiPolygon" else [geometria["coordinates"]]
    for poligono in poligonos:
        yield from poligono


def _path(geometria: dict, projetar) -> tuple[str, list[float]]:
    """`d` do SVG (anéis fechados com Z, pontos repetidos após o arredondamento caem) e a caixa projetada."""
    partes, caixa = [], [math.inf, math.inf, -math.inf, -math.inf]
    for anel in _aneis(geometria):
        pontos, anterior = [], None
        for lon, lat in anel[:-1]:
            x, y = projetar(lon, lat)
            texto = f"{x:.1f} {y:.1f}"
            if texto != anterior:
                pontos.append(texto)
                anterior = texto
            caixa = [min(caixa[0], x), min(caixa[1], y), max(caixa[2], x), max(caixa[3], y)]
        if len(pontos) >= 3:
            partes.append("M" + " ".join(pontos) + "Z")
    return "".join(partes), caixa


@lru_cache(maxsize=None)
def _desenho(cd_uf: str) -> dict:
    """Paths projetados da UF, calculados uma vez; o svg() só concatena strings."""
    base = _uf(cd_uf)
    xmin, ymin, xmax, ymax = base["bbox"]
    cosseno = math.cos(math.radians((ymin + ymax) / 2))
    escala = LADO_PX / max((xmax - xmin) * cosseno, ymax - ymin)

    def projetar(lon, lat):  # equirretangular no paralelo central da UF
        return (lon - xmin) * cosseno * escala, (ymax - lat) * escala

    paths, caixas, fundo, agua, contorno = {}, {}, [], [], ""
    for f in base["features"]:
        d, caixa = _path(f["geometry"], projetar)
        nivel = f["properties"]["nivel"]
        if nivel == "uf":
            contorno = d
            continue
        paths[f["id"]], caixas[f["id"]] = d, [round(v, 1) for v in caixa]
        (fundo if nivel == "municipio" else agua).append(d)
    largura, altura = round((xmax - xmin) * cosseno * escala, 1), round((ymax - ymin) * escala, 1)
    return {"largura": largura, "altura": altura, "fundo": "".join(fundo), "agua": "".join(agua),
            "contorno": contorno, "paths": paths, "caixas": caixas}


def svg(municipio=None, *, cep=None, largura: int = 600) -> str:
    """SVG da UF com o município em destaque (e um círculo em volta, se ele for pequeno demais para ver)."""
    cd_mun = resolver(municipio, cep)
    base, d = _uf(cd_mun[:2]), _desenho(cd_mun[:2])
    feicao = base["features"][_indice(cd_mun[:2])[cd_mun]]
    titulo = html.escape(f"{feicao['properties']['nome']} ({base['sg_uf']})")
    w, h = d["largura"], d["altura"]
    m = RAIO_MARCADOR + 4  # margem: o marcador de um município na borda não é cortado
    estilo = 'stroke-linejoin="round" vector-effect="non-scaling-stroke"'
    partes = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-m} {-m} {w + 2 * m:.1f} {h + 2 * m:.1f}" '
        f'width="{largura}" height="{round(largura * (h + 2 * m) / (w + 2 * m))}">',
        f"<title>{titulo}</title>",
        f'<path d="{d["fundo"]}" fill="{CORES["fundo"]}" fill-rule="evenodd" '
        f'stroke="{CORES["borda"]}" stroke-width="0.5" {estilo}/>',
    ]
    if d["agua"]:
        partes.append(f'<path d="{d["agua"]}" fill="{CORES["agua"]}" fill-rule="evenodd" stroke="none"/>')
    partes += [
        f'<path id="m{cd_mun}" d="{d["paths"][cd_mun]}" fill="{CORES["destaque"]}" fill-rule="evenodd" '
        f'stroke="{CORES["destaque"]}" stroke-width="0.5" {estilo}/>',
        f'<path d="{d["contorno"]}" fill="none" stroke="{CORES["uf"]}" stroke-width="1.2" {estilo}/>',
    ]
    x0, y0, x1, y1 = d["caixas"][cd_mun]
    if max(x1 - x0, y1 - y0) < RAIO_MARCADOR:
        partes.append(f'<circle cx="{(x0 + x1) / 2:.1f}" cy="{(y0 + y1) / 2:.1f}" r="{RAIO_MARCADOR}" fill="none" '
                      f'stroke="{CORES["destaque"]}" stroke-width="2" {estilo}/>')
    partes.append("</svg>")
    return "\n".join(partes)


# ---------------------------------------------------------------- JSON público (sem Python)

PROJECAO = "equirretangular no paralelo central da UF; y para baixo; lado maior = lado_px; 1 casa decimal"
RECEITA = [
    "UF = ufs[codigo[:2]]; código de 6 dígitos: o município cujo código de 7 começa por ele",
    "m = raio_marcador + 4; <svg viewBox='-m -m (largura+2m) (altura+2m)'>; <title> = nome (sigla), escapado",
    "fundo: d de todos os municípios com nivel 'municipio', concatenados; fill cores.fundo, stroke cores.borda 0.5",
    "água: d dos de nivel 'area_operacional' (lagoas do RS), fill cores.agua, sem stroke",
    "destaque: d do pedido, fill e stroke cores.destaque 0.5",
    "contorno: d da UF, sem fill, stroke cores.uf 1.2",
    "se max(x1-x0, y1-y0) da caixa do pedido < raio_marcador: círculo no centro da caixa, raio_marcador, "
    "stroke cores.destaque 2",
    "paths com fill-rule evenodd; strokes com vector-effect non-scaling-stroke",
]


def catalogo() -> dict:
    """Todas as UFs já projetadas: o necessário para montar o SVG de `svg()` em qualquer linguagem."""
    ufs = {}
    for cd_uf in sorted(c.stem for c in DIR.glob("*.json")):
        base, d = _uf(cd_uf), _desenho(cd_uf)
        ufs[cd_uf] = {
            "sigla": base["sg_uf"], "nome": base["nm_uf"], "largura": d["largura"], "altura": d["altura"],
            "contorno": d["contorno"],
            "municipios": {
                f["id"]: {"nome": f["properties"]["nome"], "nivel": f["properties"]["nivel"],
                          "caixa": d["caixas"][f["id"]], "d": d["paths"][f["id"]]}
                for f in base["features"] if f["properties"]["nivel"] != "uf"
            },
        }
    return {"formato": "geoibge-mapas/1", "edicao": _uf(next(iter(ufs)))["edicao"],
            "fonte": "IBGE, Malha Municipal (simplificada por UF)", "projecao": PROJECAO, "lado_px": LADO_PX,
            "raio_marcador": RAIO_MARCADOR, "cores": CORES, "receita": RECEITA, "ufs": ufs}


def exportar_json(destino: Path = JSON_PUBLICO) -> Path:
    """Grava o catálogo compacto (UTF-8) em `destino`, por padrão `data/mapas.json`, versionado no git."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(catalogo(), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return destino


# ---------------------------------------------------------------- exportação (banco)

# Partes de cada município (malha média) e o maior polígono de cada UF (o continente).
SQL_PARTES = """
with partes as (
    select d.cd_uf, d.cd_mun, d.nm_mun, d.is_municipio, p.geom
    from marts.dim_municipio d
    join marts.geo_municipio g using (edicao, cd_mun)
    cross join lateral st_dump(g.geom_media) p
    where d.edicao = %(edicao)s and d.cd_uf = any(%(ufs)s)
),
continente as (
    select distinct on (u.cd_uf) u.cd_uf, p.geom
    from marts.geo_uf u
    cross join lateral st_dump(u.geom_media) p
    where u.edicao = %(edicao)s and u.cd_uf = any(%(ufs)s)
    order by u.cd_uf, st_area(p.geom) desc
),
marcadas as (
    select pt.*, st_dwithin(pt.geom, c.geom, %(remota)s) as perto
    from partes pt join continente c using (cd_uf)
),
mantidas as (
    -- parte remota sai se o município tem outra perto do continente (Trindade, de Vitória);
    -- município todo remoto fica (Fernando de Noronha)
    select cd_uf, cd_mun, nm_mun, is_municipio, st_multi(st_collect(geom)) as geom
    from (select *, bool_or(perto) over (partition by cd_mun) as mun_perto from marcadas) m
    where perto or not mun_perto
    group by cd_uf, cd_mun, nm_mun, is_municipio
)
"""

SQL_EXTENSAO = SQL_PARTES + """
select u.cd_uf, u.sg_uf, u.nm_uf,
       st_xmin(e.caixa) as xmin, st_ymin(e.caixa) as ymin, st_xmax(e.caixa) as xmax, st_ymax(e.caixa) as ymax,
       (select coalesce(array_agg(distinct m.cd_mun order by m.cd_mun), '{}') from marcadas m
        where m.cd_uf = u.cd_uf and not m.perto
          and exists (select 1 from marcadas o where o.cd_mun = m.cd_mun and o.perto)) as partes_omitidas
from (select cd_uf, st_extent(geom) as caixa from mantidas group by cd_uf) e
join marts.geo_uf u on u.edicao = %(edicao)s and u.cd_uf = e.cd_uf
order by u.cd_uf
"""

# Simplificação de cobertura com a tolerância da UF: as divisas continuam encaixadas.
SQL_GEOMETRIAS = SQL_PARTES + """
, s as (
    select cd_mun, nm_mun, is_municipio, st_coveragesimplify(geom, %(tolerancia)s) over () as geom
    from mantidas
)
select * from (
    select cd_mun as id, nm_mun as nome, is_municipio,
           st_asgeojson(geom, %(decimais)s) as geometria, st_asgeojson(st_pointonsurface(geom), %(decimais)s) as ponto
    from s
    union all
    select null, null, null, st_asgeojson(st_multi(st_coverageunion(geom)), %(decimais)s), null from s
) t
order by id nulls first
"""


def parametros(xmin: float, ymin: float, xmax: float, ymax: float, lado_px: int = LADO_PX) -> tuple[float, int]:
    """Tolerância (graus) de ~1 px num desenho de `lado_px` e casas decimais com folga de 5x sobre ela."""
    cosseno = math.cos(math.radians((ymin + ymax) / 2))
    tolerancia = max((xmax - xmin) * cosseno, ymax - ymin) / lado_px
    return round(tolerancia, 6), math.ceil(-math.log10(tolerancia / 5))


def _caixa(geometria: dict) -> list[float]:
    xs, ys = zip(*(p for anel in _aneis(geometria) for p in anel))
    return [min(xs), min(ys), max(xs), max(ys)]


def montar(uf: dict, linhas: list[dict], edicao: int, tolerancia: float) -> dict:
    """FeatureCollection da UF a partir das linhas do SQL_GEOMETRIAS (a primeira, id nulo, é o contorno)."""
    contorno, *municipios = linhas
    geometria_uf = json.loads(contorno["geometria"])
    features = [{"type": "Feature", "id": uf["cd_uf"],
                 "properties": {"nivel": "uf", "nome": uf["nm_uf"], "sigla": uf["sg_uf"]},
                 "geometry": geometria_uf}]
    for linha in municipios:
        features.append({
            "type": "Feature", "id": linha["id"],
            "properties": {"nivel": "municipio" if linha["is_municipio"] else "area_operacional",
                           "nome": linha["nome"], "ponto": json.loads(linha["ponto"])["coordinates"]},
            "geometry": json.loads(linha["geometria"]),
        })
    return {"type": "FeatureCollection", "edicao": edicao, "cd_uf": uf["cd_uf"], "sg_uf": uf["sg_uf"],
            "nm_uf": uf["nm_uf"], "tolerancia": tolerancia, "partes_omitidas": list(uf["partes_omitidas"]),
            "bbox": _caixa(geometria_uf), "features": features}


def exportar(destino: Path = DIR, edicao: int | None = None, ufs: list[str] | None = None) -> list[Path]:
    """Gera um GeoJSON por UF a partir dos marts (todas, se ufs=None); compacto, UTF-8."""
    from geoibge.core import _consulta, _edicao

    edicao = _edicao(edicao)
    todas = [str(c) for c in range(11, 54)] if ufs is None else [str(u) for u in ufs]
    params = {"edicao": edicao, "remota": DISTANCIA_REMOTA}
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    gerados = []
    for uf in _consulta(SQL_EXTENSAO, {**params, "ufs": todas}).to_dict("records"):
        tolerancia, decimais = parametros(uf["xmin"], uf["ymin"], uf["xmax"], uf["ymax"])
        linhas = _consulta(SQL_GEOMETRIAS, {**params, "ufs": [uf["cd_uf"]], "tolerancia": tolerancia,
                                            "decimais": decimais}).to_dict("records")
        caminho = destino / f"{uf['cd_uf']}.json"
        caminho.write_text(json.dumps(montar(uf, linhas, edicao, tolerancia), ensure_ascii=False,
                                      separators=(",", ":")), encoding="utf-8")
        gerados.append(caminho)
    for cache in (_uf, _indice, _desenho):
        cache.cache_clear()
    return gerados
