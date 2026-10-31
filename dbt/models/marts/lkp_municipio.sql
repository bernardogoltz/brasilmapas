-- Pedaços de até 256 vértices (ST_Subdivide) com GiST: o reverse() testa bbox justo e polígono pequeno.
{{ config(indexes=[{'columns': ['geom'], 'type': 'gist'}, {'columns': ['edicao', 'cd_mun']}]) }}

with pedacos as (
    select edicao, cd_mun, nm_mun, sg_uf, is_municipio,
           st_subdivide(geom, 256) as geom
    from {{ ref('int_municipios__geom_valida') }}
)
select * from pedacos
order by edicao, st_geohash(st_centroid(geom))  -- vizinhos no espaço ficam vizinhos no disco
