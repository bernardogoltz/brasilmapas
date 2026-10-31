-- A união por UF não perde área: soma das UFs = soma dos municípios (0,01%).
with m as (select edicao, sum(st_area(geom_alta)) as a from {{ ref('geo_municipio') }} group by edicao),
     u as (select edicao, sum(st_area(geom_alta)) as a from {{ ref('geo_uf') }} group by edicao)
select m.edicao, m.a as area_mun, u.a as area_uf
from m join u using (edicao)
where abs(m.a - u.a) / m.a > 0.0001
