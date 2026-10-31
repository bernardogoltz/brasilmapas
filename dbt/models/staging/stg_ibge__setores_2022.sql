-- Setores do Censo 2022 com a hierarquia intramunicipal; situação 'Urbana'/'Rural' em minúsculas.
-- As lagoas Mirim e dos Patos (4300001/4300002) vêm sem município nem distrito: o código sai do cd_setor.
select
    cd_setor::char(15)         as cd_setor,
    lower(situacao)            as situacao,
    cd_sit,
    cd_tipo,
    cd_uf::char(2)             as cd_uf,
    coalesce(cd_mun, left(cd_setor, 7))::char(7) as cd_mun,
    nm_mun,
    cd_dist::char(9)           as cd_dist,
    nm_dist,
    cd_subdist::char(11)       as cd_subdist,
    nm_subdist,
    nullif(cd_bairro, '')      as cd_bairro,
    nullif(nm_bairro, '')      as nm_bairro,
    nullif(cd_fcu, '')         as cd_fcu,
    nullif(nm_fcu, '')         as nm_fcu,
    geom
from {{ source('raw', 'censo2022_setores') }}
