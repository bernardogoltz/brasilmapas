-- O ponto interno de cada setor cai num pedaço dele mesmo no lookup (pontos de borda podem cair no vizinho).
select s.cd_setor
from {{ ref('stg_ibge__setores_2022') }} s
where not exists (
    select 1 from {{ ref('lkp_setor') }} l
    where l.cd_setor = s.cd_setor and st_intersects(l.geom, st_pointonsurface(s.geom))
)
