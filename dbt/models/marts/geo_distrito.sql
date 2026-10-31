-- Distritos 2022: o nível útil onde não há bairros (ex.: São Paulo, 96 distritos).
{{ config(indexes=[{'columns': ['cd_dist'], 'unique': true}, {'columns': ['cd_mun']}, {'columns': ['geom'], 'type': 'gist'}]) }}

select 2022 as edicao, d.cd_dist, d.nm_dist, d.cd_uf, d.cd_mun, d.nm_mun,
       {{ poligono_valido('d.geom') }} as geom
from {{ ref('stg_ibge__distritos_2022') }} d
