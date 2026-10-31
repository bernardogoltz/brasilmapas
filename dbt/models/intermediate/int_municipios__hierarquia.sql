-- Hierarquia regional: a da malha quando existe (2025), senão a da API Localidades.
select
    g.edicao,
    g.cd_mun,
    coalesce(s.nm_uf, e.nm_uf)         as nm_uf,
    coalesce(s.cd_regiao, e.cd_regiao) as cd_regiao,
    coalesce(s.nm_regiao, e.nm_regiao) as nm_regiao,
    coalesce(s.cd_rgi, l.cd_rgi)       as cd_rgi,
    coalesce(s.nm_rgi, l.nm_rgi)       as nm_rgi,
    coalesce(s.cd_rgint, l.cd_rgint)   as cd_rgint,
    coalesce(s.nm_rgint, l.nm_rgint)   as nm_rgint,
    l.cd_mun is not null               as na_api_localidades
from {{ ref('int_municipios__geom_valida') }} g
join {{ ref('stg_ibge__municipios') }} s using (edicao, cd_mun)
left join {{ ref('stg_ibge__localidades_municipios') }} l using (cd_mun)
left join {{ ref('stg_ibge__localidades_estados') }} e on e.cd_uf = g.cd_uf
