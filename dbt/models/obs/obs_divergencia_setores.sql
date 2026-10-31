-- Métrica por edição da malha: % de setores 2022 que caem em outro município (não é teste; é tendência).
with total as (
    select count(*) as n_setores from {{ ref('stg_ibge__setores_2022') }}
),
edicoes as (
    select distinct edicao from {{ ref('lkp_municipio') }}
)
select
    e.edicao,
    t.n_setores,
    count(d.cd_setor)                                   as n_divergentes,
    count(d.cd_setor) filter (where d.cd_mun_malha is null) as n_fora_da_malha,
    round(100.0 * count(d.cd_setor) / t.n_setores, 3)   as pct_divergentes,
    now()                                               as medido_em
from edicoes e
cross join total t
left join {{ ref('obs_setores_divergentes') }} d using (edicao)
group by e.edicao, t.n_setores
