-- Arestas inválidas da cobertura por edição: as resoluções simplificadas não podem ter mais que a original.
with arestas as (
    select edicao,
           st_coverageinvalidedges(geom_alta, 0)  over w as alta,
           st_coverageinvalidedges(geom_media, 0) over w as media,
           st_coverageinvalidedges(geom_baixa, 0) over w as baixa
    from {{ ref('geo_municipio') }}
    window w as (partition by edicao)
)
select edicao, count(alta) as n_alta, count(media) as n_media, count(baixa) as n_baixa
from arestas
group by edicao
having count(media) > count(alta) or count(baixa) > count(alta)
