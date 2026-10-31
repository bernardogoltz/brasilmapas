-- Bairros 2022 (só 895 municípios têm): camada de mapa e consulta por código.
{{ config(indexes=[{'columns': ['cd_bairro'], 'unique': true}, {'columns': ['cd_mun']}, {'columns': ['geom'], 'type': 'gist'}]) }}

select 2022 as edicao, cd_bairro, nm_bairro, cd_uf, cd_mun, nm_mun, cd_dist, cd_subdist,
       {{ poligono_valido('geom') }} as geom
from {{ ref('stg_ibge__bairros_2022') }}
