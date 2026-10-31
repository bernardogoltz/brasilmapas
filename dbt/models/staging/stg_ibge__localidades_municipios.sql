-- Último retrato da API Localidades: nomes e hierarquia de referência.
with ultimo as (
    select * from {{ source('raw', 'localidades_municipios') }}
    where coletado_em = (select max(coletado_em) from {{ source('raw', 'localidades_municipios') }})
)
select
    coletado_em,
    (dados->>'municipio-id')::char(7)            as cd_mun,
    dados->>'municipio-nome'                     as nm_mun,
    (dados->>'UF-id')::char(2)                   as cd_uf,
    (dados->>'UF-sigla')::char(2)                as sg_uf,
    dados->>'UF-nome'                            as nm_uf,
    dados->>'regiao-id'                          as cd_regiao,
    dados->>'regiao-nome'                        as nm_regiao,
    dados->>'regiao-imediata-id'                 as cd_rgi,
    dados->>'regiao-imediata-nome'               as nm_rgi,
    dados->>'regiao-intermediaria-id'            as cd_rgint,
    dados->>'regiao-intermediaria-nome'          as nm_rgint
from ultimo
