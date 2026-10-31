{# Corrige só o que é inválido, garante MultiPolygon e SRID 4674 (ST_Coverage* devolvem SRID 0). #}
{% macro poligono_valido(expr) -%}
    (select st_setsrid(case when st_isvalid(g) then st_multi(g)
                            else st_multi(st_collectionextract(st_makevalid(g), 3)) end, 4674)
     from (select {{ expr }} as g) _g)
{%- endmacro %}
