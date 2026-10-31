-- Sem a feição sem código das lagoas Mirim e dos Patos (áreas operacionais, não distritos).
select
    cd_subdist::char(11) as cd_subdist,
    nm_subdist,
    cd_dist::char(9)     as cd_dist,
    nm_dist,
    cd_uf::char(2)       as cd_uf,
    cd_mun::char(7)      as cd_mun,
    nm_mun,
    geom
from {{ source('raw', 'censo2022_subdistritos') }}
where cd_subdist is not null
