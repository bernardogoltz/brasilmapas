with ultimo as (
    select * from {{ source('raw', 'localidades_estados') }}
    where coletado_em = (select max(coletado_em) from {{ source('raw', 'localidades_estados') }})
)
select
    (dados->>'UF-id')::char(2)    as cd_uf,
    (dados->>'UF-sigla')::char(2) as sg_uf,
    dados->>'UF-nome'             as nm_uf,
    dados->>'regiao-id'           as cd_regiao,
    dados->>'regiao-sigla'        as sg_regiao,
    dados->>'regiao-nome'         as nm_regiao
from ultimo
