-- Geometria em três resoluções, mais o GeoJSON da baixa pré-serializado.
{{ config(indexes=[{'columns': ['edicao', 'cd_mun'], 'unique': true}, {'columns': ['geom_alta'], 'type': 'gist'}]) }}

select
    g.edicao,
    g.cd_mun,
    g.sg_uf,
    g.geom         as geom_alta,
    s.geom_media,
    s.geom_baixa,
    st_asgeojson(s.geom_baixa, 5) as geojson_baixa
from {{ ref('int_municipios__geom_valida') }} g
join {{ ref('int_municipios__simplificado') }} s using (edicao, cd_mun)
