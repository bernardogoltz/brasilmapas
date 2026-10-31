-- Área calculada × AREA_KM2 da malha, com tolerância de 1%.
{{ config(severity='warn') }}
select edicao, cd_mun, area_km2, area_calculada_km2
from {{ ref('dim_municipio') }}
where area_km2 > 0 and abs(area_calculada_km2 - area_km2) / area_km2 > 0.01
