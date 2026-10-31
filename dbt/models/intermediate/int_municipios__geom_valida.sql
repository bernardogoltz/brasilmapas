-- Geometria corrigida (só polígonos, sempre multi) e marcação das áreas operacionais.
{{ config(indexes=[{'columns': ['edicao', 'cd_mun'], 'unique': true}, {'columns': ['geom'], 'type': 'gist'}]) }}

select
    m.edicao,
    m.cd_mun,
    m.nm_mun,
    m.cd_uf,
    m.sg_uf,
    m.area_km2,
    a.cd_mun is null as is_municipio,
    {{ poligono_valido('m.geom') }} as geom
from {{ ref('stg_ibge__municipios') }} m
left join {{ ref('areas_operacionais') }} a on a.cd_mun::text = m.cd_mun
