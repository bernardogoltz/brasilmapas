{# Usa o schema da camada como está (staging, marts…), sem prefixo do target. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ custom_schema_name or target.schema }}
{%- endmacro %}
