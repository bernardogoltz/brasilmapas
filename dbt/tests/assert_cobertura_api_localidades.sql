-- Todo município da API existe na malha mais recente (e vice-versa, fora as áreas operacionais).
with ultima as (
    select * from {{ ref('dim_municipio') }}
    where edicao = (select max(edicao) from {{ ref('dim_municipio') }})
)
select coalesce(u.cd_mun, l.cd_mun) as cd_mun,
       case when u.cd_mun is null then 'falta na malha' else 'falta na API' end as problema
from ultima u
full join {{ ref('stg_ibge__localidades_municipios') }} l using (cd_mun)
where (u.cd_mun is null or l.cd_mun is null) and coalesce(u.is_municipio, true)
