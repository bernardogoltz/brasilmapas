-- Sem a feição sem código das lagoas Mirim e dos Patos (áreas operacionais, não distritos).
select
    cd_dist::char(9) as cd_dist,
    nm_dist,
    cd_uf::char(2)   as cd_uf,
    cd_mun::char(7)  as cd_mun,
    nm_mun,
    geom
from {{ source('raw', 'censo2022_distritos') }}
where cd_dist is not null
