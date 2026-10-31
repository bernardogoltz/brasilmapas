-- Setores 2022 subdivididos (ST_Subdivide 256) com a hierarquia intramunicipal inteira, para o reverse().
{{ config(indexes=[{'columns': ['geom'], 'type': 'gist'}, {'columns': ['cd_setor']}]) }}

with pedacos as (
    select 2022 as edicao, s.cd_setor, s.situacao, s.cd_mun,
           s.cd_dist, s.nm_dist, s.cd_subdist, s.nm_subdist, s.cd_bairro, s.nm_bairro, s.cd_fcu, s.nm_fcu,
           st_subdivide({{ poligono_valido('s.geom') }}, 256) as geom
    from {{ ref('stg_ibge__setores_2022') }} s
)
select * from pedacos
order by st_geohash(st_centroid(geom))  -- vizinhos no espaço ficam vizinhos no disco
