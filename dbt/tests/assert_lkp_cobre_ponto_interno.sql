-- O ponto interno de cada município cai num pedaço dele mesmo no lookup do reverse().
select d.edicao, d.cd_mun
from {{ ref('dim_municipio') }} d
where not exists (
    select 1 from {{ ref('lkp_municipio') }} l
    where l.edicao = d.edicao and l.cd_mun = d.cd_mun and st_intersects(l.geom, d.ponto_interno)
)
