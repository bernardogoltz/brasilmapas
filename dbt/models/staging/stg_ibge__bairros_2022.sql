-- Bairros 2022: agrega por código (o GPKG repete feições do mesmo bairro; o SHP não, mas não custa).
select
    cd_bairro,
    min(nm_bairro)  as nm_bairro,
    min(cd_uf)::char(2)       as cd_uf,
    min(cd_mun)::char(7)      as cd_mun,
    min(nm_mun)     as nm_mun,
    min(cd_dist)::char(9)     as cd_dist,
    min(cd_subdist)::char(11) as cd_subdist,
    st_union(geom)  as geom
from {{ source('raw', 'censo2022_bairros') }}
group by cd_bairro
