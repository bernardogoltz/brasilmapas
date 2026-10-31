-- Edição publicada: a padrão da biblioteca geoibge. Hoje, a mais recente com marts completos.
{{ config(schema='meta') }}

select max(edicao) as edicao, now() as publicado_em
from {{ ref('dim_municipio') }}
