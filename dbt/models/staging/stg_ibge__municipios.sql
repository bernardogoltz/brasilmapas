-- Malha municipal padronizada entre edições: 2019 não traz cd_uf nem a hierarquia regional.
select
    _edicao                                   as edicao,
    cd_mun::char(7)                           as cd_mun,
    nm_mun,
    coalesce(cd_uf, left(cd_mun, 2))::char(2) as cd_uf,
    sigla_uf::char(2)                         as sg_uf,
    nm_uf,
    cd_regiao,
    nm_regiao,
    cd_rgi,
    nm_rgi,
    cd_rgint,
    nm_rgint,
    area_km2,
    geom
from {{ source('raw', 'br_municipios') }}
