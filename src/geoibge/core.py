"""Consultas aos marts: ufs(), municipios(), reverse(), validar() e edicoes().

Tudo roda no banco numa consulta por chamada (listas via unnest); a geometria vem como WKB.
"""

import os
import re

import geopandas as gpd
import pandas as pd
import psycopg
import shapely

DSN_PADRAO = "postgresql://api_reader:api_reader@localhost:5432/geo"
RESOLUCOES = ("alta", "media", "baixa")
SIGLAS = set("AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO".split())
TOLERANCIA_AREA_PCT = 1.0

_conn: psycopg.Connection | None = None


def conectar(dsn: str | None = None) -> psycopg.Connection:
    """Abre (ou reabre) a conexão; padrão em GEOIBGE_DSN."""
    global _conn
    if _conn is not None and not _conn.closed and dsn is None:
        return _conn
    if _conn is not None:
        _conn.close()
    _conn = psycopg.connect(dsn or os.environ.get("GEOIBGE_DSN", DSN_PADRAO), autocommit=True)
    return _conn


def _consulta(sql: str, params: dict | None = None) -> pd.DataFrame:
    with conectar().cursor() as cur:
        cur.execute(sql, params or {})
        colunas = [c.name for c in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=colunas)


def _gdf(df: pd.DataFrame, **attrs) -> gpd.GeoDataFrame:
    geom = shapely.from_wkb(df.pop("geom").map(bytes).to_numpy()) if len(df) else []
    gdf = gpd.GeoDataFrame(df, geometry=gpd.GeoSeries(geom, index=df.index), crs="EPSG:4674")
    gdf.attrs.update(attrs)
    return gdf


# ---------------------------------------------------------------- entrada


def _resolucao(resolucao: str) -> str:
    if resolucao not in RESOLUCOES:
        raise ValueError(f"resolucao deve ser uma de {RESOLUCOES}, não {resolucao!r}")
    return resolucao


def normalizar_uf(item) -> tuple[str, str]:
    """'SP' → ('sigla', 'SP'); 35 ou '35' → ('codigo', '35')."""
    texto = str(item).strip().upper()
    if texto in SIGLAS:
        return "sigla", texto
    if re.fullmatch(r"[1-5]\d", texto):
        return "codigo", texto
    raise ValueError(f"UF inválida: {item!r}")


def normalizar_municipio(item) -> tuple[str, str, str | None]:
    """3550308 → ('cd7', …); '355030' → ('cd6', …); ('Bom Jesus', 'PI') → ('nome', 'Bom Jesus', 'PI')."""
    if isinstance(item, tuple):
        if len(item) != 2:
            raise ValueError(f"esperado (nome, uf): {item!r}")
        nome, uf = item
        tipo, sigla = normalizar_uf(uf)
        if tipo != "sigla":
            raise ValueError(f"use a sigla da UF em (nome, uf): {item!r}")
        return "nome", str(nome).strip(), sigla
    texto = str(item).strip()
    if re.fullmatch(r"\d{7}", texto):
        return "cd7", texto, None
    if re.fullmatch(r"\d{6}", texto):
        return "cd6", texto, None
    raise ValueError(f"município inválido: {item!r} (código de 6 ou 7 dígitos, ou (nome, uf))")


def _lista(ids) -> list:
    if ids is None or isinstance(ids, list):
        return ids
    if isinstance(ids, (str, int, tuple)):
        return [ids]
    return list(ids)


def _normalizar_todos(ids, funcao) -> list:
    normalizados, erros = [], []
    for item in ids:
        try:
            normalizados.append(funcao(item))
        except ValueError as e:
            erros.append(str(e))
    if erros:
        raise ValueError("; ".join(erros))
    return normalizados


def normalizar_pontos(pontos, lat: str = "lat", lon: str = "lon") -> pd.DataFrame:
    """Tupla (lat, lon), lista de tuplas ou DataFrame → DataFrame com lat e lon (índice preservado)."""
    if isinstance(pontos, pd.DataFrame):
        df = pd.DataFrame({"lat": pontos[lat], "lon": pontos[lon]}, index=pontos.index)
    else:
        if isinstance(pontos, tuple) and len(pontos) == 2 and not isinstance(pontos[0], (tuple, list)):
            pontos = [pontos]
        df = pd.DataFrame(list(pontos), columns=["lat", "lon"])
    df = df.astype(float)
    df["erro"] = None
    invalido = ~(df.lat.between(-90, 90) & df.lon.between(-180, 180))  # NaN também cai aqui
    df.loc[invalido, "erro"] = "coordenada_invalida"
    return df


# ---------------------------------------------------------------- edição


def edicoes() -> pd.DataFrame:
    """Edições carregadas e qual é a publicada."""
    return _consulta("""
        select d.edicao, count(*) filter (where d.is_municipio) as n_municipios,
               d.edicao = (select edicao from meta.publicacao) as publicada
        from marts.dim_municipio d group by d.edicao order by d.edicao
    """)


def _edicao(edicao: int | None) -> int:
    if edicao is not None:
        return int(edicao)
    df = _consulta("select edicao from meta.publicacao")
    if df.empty or pd.isna(df.edicao[0]):
        raise RuntimeError("nenhuma edição publicada em meta.publicacao")
    return int(df.edicao[0])


# ---------------------------------------------------------------- consultas


def ufs(ids=None, resolucao: str = "media", edicao: int | None = None) -> gpd.GeoDataFrame:
    """GeoDataFrame das UFs (todas, se ids=None); aceita sigla ou código."""
    resolucao, edicao, ids = _resolucao(resolucao), _edicao(edicao), _lista(ids)
    df = _consulta(f"""
        select edicao, cd_uf, sg_uf, nm_uf, n_municipios, area_km2, st_asbinary(geom_{resolucao}) as geom
        from marts.geo_uf where edicao = %(edicao)s order by cd_uf
    """, {"edicao": edicao})
    if ids is not None:
        pedidos = _normalizar_todos(ids, normalizar_uf)
        por_sigla, por_codigo = df.set_index("sg_uf", drop=False), df.set_index("cd_uf", drop=False)
        linhas, faltando = [], []
        for tipo, valor in pedidos:
            tabela = por_sigla if tipo == "sigla" else por_codigo
            if valor in tabela.index:
                linhas.append(tabela.loc[valor])
            else:
                faltando.append(valor)
        if faltando:
            raise ValueError(f"UF sem dado na edição {edicao}: {', '.join(faltando)}")
        df = pd.DataFrame(linhas).reset_index(drop=True)
    return _gdf(df, edicao=edicao, resolucao=resolucao, camada="uf")


SQL_RESOLVER = """
with e as (
    select * from unnest(%(pos)s::int[], %(tipo)s::text[], %(valor)s::text[], %(uf)s::text[]) as t(pos, tipo, valor, uf)
)
select e.pos, e.valor, d.cd_mun
from e
left join marts.dim_municipio d on d.edicao = %(edicao)s and (
       (e.tipo = 'cd7'  and d.cd_mun = e.valor)
    or (e.tipo = 'cd6'  and d.cd_mun6 = e.valor)
    or (e.tipo = 'nome' and d.nm_busca = lower(unaccent(e.valor)) and d.sg_uf = e.uf)
)
order by e.pos, d.cd_mun
"""

COLUNAS_MUNICIPIO = """
    d.edicao, d.cd_mun, d.cd_mun6, d.nm_mun, d.is_municipio, d.cd_uf, d.sg_uf, d.nm_uf,
    d.cd_regiao, d.nm_regiao, d.cd_rgi, d.nm_rgi, d.cd_rgint, d.nm_rgint, d.area_km2,
    d.bbox_xmin, d.bbox_ymin, d.bbox_xmax, d.bbox_ymax
"""


def _resolver_municipios(ids: list, edicao: int) -> list[str]:
    pedidos = _normalizar_todos(ids, normalizar_municipio)
    achados = _consulta(SQL_RESOLVER, {
        "pos": list(range(len(pedidos))),
        "tipo": [p[0] for p in pedidos],
        "valor": [p[1] for p in pedidos],
        "uf": [p[2] for p in pedidos],
        "edicao": edicao,
    })
    erros, codigos = [], []
    for pos, grupo in achados.groupby("pos", sort=True):
        item = ids[pos]
        if grupo.cd_mun.isna().all():
            erros.append(f"{item!r} inexistente na edição {edicao}")
        elif len(grupo) > 1:
            erros.append(f"{item!r} ambíguo: {', '.join(grupo.cd_mun)}")
        else:
            codigos.append(grupo.cd_mun.iloc[0])
    if erros:
        raise ValueError("; ".join(erros))
    return codigos


def municipios(ids=None, uf=None, resolucao: str = "media", edicao: int | None = None) -> gpd.GeoDataFrame:
    """Municípios por código (6 ou 7 dígitos) ou (nome, uf); ou todos de uma UF; na ordem pedida."""
    resolucao, edicao, ids = _resolucao(resolucao), _edicao(edicao), _lista(ids)
    if ids is None and uf is None:
        raise ValueError("informe ids ou uf")
    filtros, params = ["d.edicao = %(edicao)s"], {"edicao": edicao}
    if ids is not None:
        codigos = _resolver_municipios(ids, edicao)
        filtros.append("d.cd_mun = any(%(codigos)s)")
        params["codigos"] = codigos
    if uf is not None:
        tipo, valor = normalizar_uf(uf)
        filtros.append("d.sg_uf = %(uf)s" if tipo == "sigla" else "d.cd_uf = %(uf)s")
        params["uf"] = valor
    df = _consulta(f"""
        select {COLUNAS_MUNICIPIO}, st_asbinary(g.geom_{resolucao}) as geom
        from marts.dim_municipio d
        join marts.geo_municipio g using (edicao, cd_mun)
        where {' and '.join(filtros)}
        order by d.cd_mun
    """, params)
    if ids is not None:
        df = df.set_index("cd_mun", drop=False).loc[[c for c in dict.fromkeys(codigos) if c in set(df.cd_mun)]]
        df = df.reset_index(drop=True)
    return _gdf(df, edicao=edicao, resolucao=resolucao, camada="municipio")


SQL_REVERSE = """
with p as (
    select id, st_setsrid(st_makepoint(lon, lat), 4674) as geom
    from unnest(%(ids)s::int[], %(lons)s::float8[], %(lats)s::float8[]) as t(id, lon, lat)
)
select p.id, coalesce(m.cd_mun, n.cd_mun) as cd_mun, m.cd_mun is null and n.cd_mun is not null as proximo{colunas_setor}
from p
left join lateral (
    select l.cd_mun from marts.lkp_municipio l
    where l.edicao = %(edicao)s and st_intersects(l.geom, p.geom)
    order by l.cd_mun  -- ponto exatamente na divisa: desempate determinístico
    limit 1
) m on true
left join lateral (
    -- ponto na costa, fora da malha: município mais próximo até 1 km
    select l.cd_mun from marts.lkp_municipio l
    where m.cd_mun is null and l.edicao = %(edicao)s
      and l.geom && st_expand(p.geom, 0.02)
      and st_dwithin(l.geom::geography, p.geom::geography, 1000)
    order by l.geom <-> p.geom
    limit 1
) n on true
{setor}
"""

# Hierarquia intramunicipal do Censo 2022: sem filtro de edição (dado único)
SQL_REVERSE_SETOR = """
left join lateral (
    select l.cd_setor, l.situacao, l.cd_mun as cd_mun_setor, l.cd_dist, l.nm_dist,
           l.cd_subdist, l.nm_subdist, l.cd_bairro, l.nm_bairro, l.cd_fcu, l.nm_fcu
    from marts.lkp_setor l
    where st_intersects(l.geom, p.geom)
    order by l.cd_setor
    limit 1
) s on true
"""
COLUNAS_SETOR = ["cd_setor", "situacao", "cd_mun_setor", "cd_dist", "nm_dist", "cd_subdist", "nm_subdist",
                 "cd_bairro", "nm_bairro", "cd_fcu", "nm_fcu"]


def _tem_setores() -> bool:
    return _consulta("select to_regclass('marts.lkp_setor') is not null as ok").ok[0]


def _avisos(linha) -> str | None:
    avisos = []
    if linha.proximo == True:  # noqa: E712 (NaN quando não há ponto válido)
        avisos.append("fora da malha; município mais próximo até 1 km")
    if isinstance(linha.cd_mun, str):
        if not isinstance(linha.cd_setor, str):
            avisos.append("sem setor 2022 no ponto")
        else:
            if linha.cd_mun_setor != linha.cd_mun:
                avisos.append(f"setor 2022 é de {linha.cd_mun_setor}: a malha mudou depois do Censo")
            if not isinstance(linha.cd_bairro, str) and isinstance(linha.cd_dist, str):
                avisos.append("sem bairro na malha 2022; distrito informado")
    return "; ".join(avisos) or None


def sql_reverse(setores: bool = True) -> str:
    """SQL do reverse(): município (edição pedida) e, se houver lkp_setor, a hierarquia do Censo 2022."""
    if not setores:
        return SQL_REVERSE.format(colunas_setor="", setor="")
    return SQL_REVERSE.format(colunas_setor=", " + ", ".join(f"s.{c}" for c in COLUNAS_SETOR), setor=SQL_REVERSE_SETOR)


def reverse(pontos, lat: str = "lat", lon: str = "lon", edicao: int | None = None) -> pd.DataFrame:
    """Hierarquia de cada ponto (UF, município, regiões; setor, distrito, subdistrito e bairro 2022), numa ida ao banco."""
    edicao = _edicao(edicao)
    df = normalizar_pontos(pontos, lat, lon)
    validos = df[df.erro.isna()]
    achados = _consulta(sql_reverse(_tem_setores()), {
        "ids": list(range(len(validos))),
        "lons": validos.lon.tolist(),
        "lats": validos.lat.tolist(),
        "edicao": edicao,
    }) if len(validos) else pd.DataFrame(columns=["id", "cd_mun", "proximo"])
    achados = achados.reindex(columns=[*achados.columns, *(c for c in COLUNAS_SETOR if c not in achados)])
    codigos = sorted(set(achados.cd_mun.dropna()))
    atributos = _consulta(f"""
        select d.cd_mun, d.nm_mun, d.cd_uf, d.sg_uf, d.nm_uf, d.cd_rgi, d.nm_rgi, d.cd_rgint, d.nm_rgint, d.is_municipio
        from marts.dim_municipio d where d.edicao = %(edicao)s and d.cd_mun = any(%(codigos)s)
    """, {"edicao": edicao, "codigos": codigos})
    achados.index = validos.index[achados.id.astype(int)] if len(achados) else achados.index
    out = df.join(achados.drop(columns="id")).merge(atributos, on="cd_mun", how="left").set_axis(df.index)
    out["edicao"] = edicao
    out["aviso"] = out.apply(_avisos, axis=1) if len(out) else None
    sem = out.erro.isna() & out.cd_mun.isna()
    out.loc[sem, "erro"] = "fora_do_brasil"
    return out.drop(columns=["proximo", "cd_mun_setor"])


def validar(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """Relatório por feição, calculado no banco pelas chaves do gdf (sem enviar geometria)."""
    edicao, resolucao = gdf.attrs.get("edicao"), gdf.attrs.get("resolucao", "media")
    _resolucao(resolucao)
    if "cd_mun" in gdf:
        chave, tabela, area = "cd_mun", "marts.geo_municipio g join marts.dim_municipio d using (edicao, cd_mun)", "d.area_km2"
    elif "cd_uf" in gdf:
        chave, tabela, area = "cd_uf", "marts.geo_uf g", "g.area_km2"
    else:
        raise ValueError("gdf sem cd_mun nem cd_uf: use o retorno de municipios() ou ufs()")
    edicao = _edicao(edicao if edicao is not None else (gdf.edicao.iloc[0] if "edicao" in gdf and len(gdf) else None))
    geom = f"g.geom_{resolucao}"
    df = _consulta(f"""
        select {chave} as codigo,
               st_isvalid({geom}) as valida,
               nullif(st_isvalidreason({geom}), 'Valid Geometry') as motivo,
               st_srid({geom}) as srid,
               {area}::float8 as area_km2,
               (st_area(g.geom_alta::geography) / 1e6)::float8 as area_calculada_km2,
               st_npoints({geom}) as vertices,
               octet_length(st_asgeojson({geom}, 5)) as geojson_bytes
        from {tabela}
        where g.edicao = %(edicao)s and {chave} = any(%(codigos)s)
    """, {"edicao": edicao, "codigos": [str(c) for c in gdf[chave]]})
    df = df.set_index("codigo").reindex([str(c) for c in gdf[chave]]).reset_index()
    df["dif_area_pct"] = (df.area_calculada_km2 / df.area_km2 - 1).abs() * 100
    df["ok"] = df.valida.eq(True) & df.srid.eq(4674) & df.dif_area_pct.le(TOLERANCIA_AREA_PCT)
    df.insert(1, "edicao", edicao)
    df.insert(2, "resolucao", resolucao)
    return df

