select edicao, count(*) as n from {{ ref('geo_uf') }} group by edicao having count(*) <> 27
