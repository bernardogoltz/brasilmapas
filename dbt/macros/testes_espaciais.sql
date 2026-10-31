{# Testes genéricos de geometria. Cada um devolve as linhas que falham. #}

{% test geometria_valida(model, column_name) %}
select * from {{ model }}
where {{ column_name }} is null or not st_isvalid({{ column_name }}) or st_isempty({{ column_name }})
{% endtest %}

{% test srid(model, column_name, srid=4674) %}
select * from {{ model }} where st_srid({{ column_name }}) <> {{ srid }}
{% endtest %}

{% test chave_unica(model, colunas) %}
select {{ colunas | join(', ') }}, count(*) as n
from {{ model }}
group by {{ colunas | join(', ') }}
having count(*) > 1
{% endtest %}

{# Arestas inválidas da cobertura (frestas e sobreposições entre vizinhos), por partição. #}
{% test cobertura_valida(model, column_name, particao, tolerancia=0) %}
select * from (
    select {{ particao }}, st_coverageinvalidedges({{ column_name }}, {{ tolerancia }}) over (partition by {{ particao }}) as aresta
    from {{ model }}
) x
where aresta is not null
{% endtest %}
