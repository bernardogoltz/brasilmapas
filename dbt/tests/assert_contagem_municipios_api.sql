-- Edição mais recente: municípios da malha = municípios da API Localidades (5.571 em 2025).
with malha as (
    select count(*) filter (where is_municipio) as n
    from {{ ref('dim_municipio') }}
    where edicao = (select max(edicao) from {{ ref('dim_municipio') }})
),
api as (select count(*) as n from {{ ref('stg_ibge__localidades_municipios') }})
select malha.n as malha, api.n as api from malha, api where malha.n <> api.n
