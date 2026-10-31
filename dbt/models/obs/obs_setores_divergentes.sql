-- Setores 2022 cujo ponto interno cai em outro município (ou fora) na malha de cada edição carregada.
with setores as materialized (  -- senão o ponto interno é recalculado dentro do lateral
    select cd_setor, cd_mun, st_pointonsurface(geom) as ponto
    from {{ ref('stg_ibge__setores_2022') }}
),
edicoes as (
    select distinct edicao from {{ ref('lkp_municipio') }}
)
select e.edicao, s.cd_setor, s.cd_mun as cd_mun_censo, m.cd_mun as cd_mun_malha
from setores s
cross join edicoes e
left join lateral (
    select l.cd_mun from {{ ref('lkp_municipio') }} l
    where l.edicao = e.edicao and st_intersects(l.geom, s.ponto)
    order by l.cd_mun
    limit 1
) m on true
where m.cd_mun is distinct from s.cd_mun
