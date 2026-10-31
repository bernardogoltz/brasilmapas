-- Simplifica a cobertura de cada edição de uma vez: divisas compartilhadas continuam batendo.
select
    edicao,
    cd_mun,
    st_setsrid(st_multi(st_coveragesimplify(geom, {{ var('tolerancia_media') }}) over (partition by edicao)), 4674) as geom_media,
    st_setsrid(st_multi(st_coveragesimplify(geom, {{ var('tolerancia_baixa') }}) over (partition by edicao)), 4674) as geom_baixa
from {{ ref('int_municipios__geom_valida') }}
