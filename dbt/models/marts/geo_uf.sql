-- UF = união da cobertura dos seus municípios (mesmas divisas, nas três resoluções).
{{ config(indexes=[{'columns': ['edicao', 'cd_uf'], 'unique': true}, {'columns': ['geom_alta'], 'type': 'gist'}]) }}

select
    g.edicao,
    g.cd_uf,
    g.sg_uf,
    e.nm_uf,
    count(*) filter (where g.is_municipio)          as n_municipios,
    {{ poligono_valido('st_coverageunion(g.geom)') }}             as geom_alta,
    {{ poligono_valido('st_coverageunion(s.geom_media)') }}       as geom_media,
    {{ poligono_valido('st_coverageunion(s.geom_baixa)') }}       as geom_baixa,
    round(sum(g.area_km2)::numeric, 3)             as area_km2
from {{ ref('int_municipios__geom_valida') }} g
join {{ ref('int_municipios__simplificado') }} s using (edicao, cd_mun)
left join {{ ref('stg_ibge__localidades_estados') }} e on e.cd_uf = g.cd_uf
group by g.edicao, g.cd_uf, g.sg_uf, e.nm_uf
