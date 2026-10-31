-- Atributos do município, sem geometria: códigos, nomes, hierarquia, bbox e ponto interno.
{{ config(
    indexes=[{'columns': ['edicao', 'cd_mun'], 'unique': true}, {'columns': ['cd_mun6']}],
    post_hook='create index on {{ this }} using gin (nm_busca gin_trgm_ops)',
) }}

select
    g.edicao,
    g.cd_mun,
    left(g.cd_mun, 6)                        as cd_mun6,
    g.nm_mun,
    lower(unaccent(g.nm_mun))                as nm_busca,
    g.is_municipio,
    g.cd_uf,
    g.sg_uf,
    h.nm_uf,
    h.cd_regiao,
    h.nm_regiao,
    h.cd_rgi,
    h.nm_rgi,
    h.cd_rgint,
    h.nm_rgint,
    h.na_api_localidades,
    g.area_km2,
    round((st_area(g.geom::geography) / 1e6)::numeric, 3) as area_calculada_km2,
    st_xmin(g.geom) as bbox_xmin,
    st_ymin(g.geom) as bbox_ymin,
    st_xmax(g.geom) as bbox_xmax,
    st_ymax(g.geom) as bbox_ymax,
    st_pointonsurface(g.geom) as ponto_interno
from {{ ref('int_municipios__geom_valida') }} g
join {{ ref('int_municipios__hierarquia') }} h using (edicao, cd_mun)
