# IBGE Dados Geográficos

Projeto de estudo de engenharia de dados: um pipeline que ingere as malhas territoriais do IBGE, modela com **dbt**, orquestra com **Airflow**, explora com **marimo**, monitora com **Grafana** e entrega os dados numa **biblioteca Python**, tudo local com **Docker Compose**.

> **Status: fases 0 a 5 implementadas** (ingestão, dbt, `geoibge`, Martin, Censo 2022 intramunicipal e observabilidade com Grafana); pendentes: elementary e alertas. Caminhos, colunas e contagens das fontes foram conferidos direto no IBGE em 30/10/2026.

## Comandos

Tudo passa pelo `make` (requer Docker e `uv`). `make` sozinho lista os comandos.

| Comando | O que faz |
|---|---|
| `make up` | cria o `.env` se faltar, sobe os containers, espera ficarem saudáveis e mostra o status |
| `make airflow` | sobe banco + Airflow (build da imagem; UI em `localhost:8080`) |
| `make dags-check` | lista erros de import das DAGs, no container |
| `make carregar` | dispara `ibge_malha_municipal`; `EDICAO=2019` para backfill |
| `make localidades` | dispara `ibge_localidades` |
| `make censo` | dispara `ibge_censo2022_intramunicipal` (setores, bairros, distritos, subdistritos); `FORCAR=1` recarrega |
| `make dbt` | `dbt build` local (staging → marts + testes) contra o banco do compose |
| `make transformar` | dispara `dbt_geo` (Cosmos) no Airflow; também roda sozinha quando a ingestão atualiza um asset |
| `make tiles` | sobe o Martin com municípios e UFs como vector tiles (`localhost:3001`) |
| `make validar` | valida UFs e municípios com o `geoibge`; `IDS="SP 3550308"` |
| `make mapas` | regera `src/geoibge/mapas/{cd_uf}.json` (GeoJSON por UF, simplificado na escala da UF) a partir dos marts, e o `data/mapas.json` |
| `make mapas-json` | regera `data/mapas.json` (paths SVG prontos de todas as UFs, para uso externo) a partir dos GeoJSON, sem banco |
| `make mapa` | SVG da UF com o município em destaque, sem banco: `COD=3550308` ou `CEP=01310-100`; grava em `data/mapas/` |
| `make explorador` | app `05_explorador.py`: UF → mapa, clique → `reverse()` |
| `make simplificacao` | abre `02_simplificacao.py` (tolerância × tamanho × frestas) |
| `make benchmark` | abre `03_benchmark_reverse.py` (latência e lote do `reverse()`) |
| `make obs` | sobe Prometheus, exporters e Grafana (`localhost:3000`) e garante o papel `monitor` |
| `make tour` | abre `06_tour.py`: tour final da `geoibge`, do dado ao mapa |
| `make down` | para os containers de todos os profiles (os dados ficam no volume) |
| `make status` | serviços: estado, porta, uptime, CPU e memória |
| `make notebook` | abre `01_explorar_fontes.py` no marimo (baixa a malha da UF escolhida) |
| `make test` | roda os testes em `tests/` (pytest) |

## Serviços

Endereços com as portas padrão do `.env.example`.

| Serviço | Container | Endereço | Acesso |
|---|---|---|---|
| PostgreSQL + PostGIS | `postgis` | `localhost:5432` (`POSTGRES_PORT`) | `postgres`/`postgres`; bancos `geo` e `airflow` |
| Airflow UI e API | `airflow-apiserver` | http://localhost:8080 (`AIRFLOW_PORT`) | sem login (todos admin) |
| Airflow scheduler | `airflow-scheduler` | interno (health em `:8974`) | — |
| Airflow DAG processor | `airflow-dag-processor` | interno | — |
| Airflow triggerer | `airflow-triggerer` | interno | — |
| Martin (vector tiles) | `martin` | http://localhost:3001/catalog (`MARTIN_PORT`) | camadas `municipios` e `ufs`; papel `api_reader` |
| Grafana | `grafana` | http://localhost:3000 (`GRAFANA_PORT`) | sem login; dashboards Pipeline, Qualidade e Banco |
| Prometheus | `prometheus` | http://localhost:9090 (`PROMETHEUS_PORT`) | — |
| StatsD exporter | `statsd-exporter` | `localhost:9102` (UDP 9125 interno) | recebe as métricas do Airflow |
| Postgres exporter | `postgres-exporter` | `localhost:9187` | papel `monitor` |
| marimo | local (`make notebook`) | http://localhost:2718 | token na URL impressa |

Papéis do banco `geo`: `loader`, `transformer`, `api_reader`, `monitor` (senhas no `.env`). Os serviços Airflow só sobem com o profile `airflow` (`make airflow`); o Martin, com o `core` (`make tiles`); a observabilidade, com o `obs` (`make obs`).

A biblioteca `geoibge` conecta por `GEOIBGE_DSN` (padrão `postgresql://api_reader:api_reader@localhost:5432/geo`).

## Objetivo

Responder três perguntas, rápido e com a origem de cada dado explícita:

| Pergunta | Entrada | Saída |
|---|---|---|
| Mostre estes municípios | lista de códigos IBGE (`3550308`) ou nomes + UF (`São Paulo`, `SP`) | atributos, hierarquia, bbox, geometria em 3 resoluções e validação |
| Mostre estes estados | lista de siglas ou códigos (`SP`, `35`) | geometria das UFs e dos seus municípios, com validação |
| Onde fica este ponto? | `lat`, `lon` (um ponto ou um lote) | UF, município, regiões imediata e intermediária, distrito, subdistrito, bairro, setor censitário, situação urbana/rural |

Metas (a validar com benchmark):

- `reverse()` de um ponto com p95 < 50 ms; lote de 100 mil pontos em < 60 s.
- `municipios()` de um código com p95 < 100 ms; validação de uma UF inteira em < 5 s; resolução baixa < 50 KB.
- Pipeline idempotente e reprocessável por edição da malha.
- Toda resposta informa a edição de cada camada (ex.: malha 2025, setores 2022).

## Arquitetura

```mermaid
flowchart LR
    subgraph fontes["Fontes IBGE"]
        ftp["geoftp<br/>malhas SHP/GPKG"]
        loc["API Localidades<br/>JSON"]
    end

    subgraph orq["Airflow"]
        dags["DAGs<br/>descobrir → baixar → validar → carregar"]
    end

    subgraph pg["PostgreSQL + PostGIS"]
        raw[("raw")]
        stg[("staging / intermediate")]
        marts[("marts")]
    end

    subgraph serving["Serving"]
        lib["Biblioteca Python<br/>ufs() municipios() reverse() validar()"]
        pmtiles["PMTiles<br/>tippecanoe"]
        martin["Martin<br/>vector tiles"]
    end

    subgraph obs["Observabilidade"]
        prom["Prometheus"]
        grafana["Grafana"]
    end

    marimo["marimo<br/>exploração e QA"]
    qgis["QGIS<br/>vector tiles"]

    ftp --> dags
    loc --> dags
    dags -->|ogr2ogr| raw
    raw -->|dbt| stg
    stg -->|dbt| marts
    marts --> lib
    marts --> martin
    marts --> pmtiles
    pmtiles --> martin
    lib --> marimo
    martin --> qgis
    marts --> marimo
    dags -.->|métricas| prom
    prom --> grafana
    marts -.->|testes dbt| grafana
```

| Peça | Ferramenta | Papel |
|---|---|---|
| Ambiente | Docker Compose com `profiles` | sobe o stack inteiro ou por partes |
| Banco | PostgreSQL 18 + PostGIS 3.6 | warehouse **e** serving: camadas do dbt, índices GiST, consultas espaciais |
| Ingestão | GDAL `ogr2ogr` | lê SHP/GPKG de dentro do zip e grava no PostGIS |
| Orquestração | Apache Airflow 3 (LocalExecutor) | agenda, retries, assets, backfill por edição |
| Transformação | dbt-core + dbt-postgres | modelos SQL/PostGIS, testes, docs e linhagem |
| dbt no Airflow | astronomer-cosmos | cada modelo e teste do dbt vira uma task |
| Qualidade | testes do dbt + pacote elementary | resultados dos testes em tabelas, lidas pelo Grafana |
| Exploração | marimo | notebooks reativos em `.py` (versionáveis): exploração, QA visual, benchmarks |
| Interface | biblioteca Python (`geoibge`) | `ufs()`, `municipios()`, `reverse()`, `validar()`; retorna GeoDataFrame |
| Tiles | Martin + tippecanoe (PMTiles) | vector tiles para QGIS e notebooks |
| Métricas | Prometheus + statsd-exporter + postgres-exporter | coleta de Airflow e banco |
| Dashboards e alertas | Grafana | pipeline, qualidade e banco |
| Python local | uv | dependências e ambientes |

Versões de referência (PyPI, Docker Hub e GitHub em 30/10/2026): Airflow 3.3.2 · astronomer-cosmos 1.15.1 · dbt-core 1.12.6 · dbt-postgres 1.11.0 · marimo 0.25.2 · imagem `postgis/postgis:18-3.6` · Martin 1.16.0 · tippecanoe 2.79.0 · Grafana 13.3.0. Fixar no `pyproject.toml` e no compose ao implementar.

## Fontes de dados

Todas públicas, do IBGE. Abreviações: `$GEOFTP` = `https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais`; `$API` = `https://servicodados.ibge.gov.br/api`.

| Camada | Caminho | Formato e tamanho | Registros | Uso |
|---|---|---|---|---|
| Municípios 2025 (edição mais recente) | `$GEOFTP/malhas_municipais/municipio_2025/Brasil/BR_Municipios_2025.zip` | SHP zip, 226 MB | 5.573 feições | geometria do município (fonte principal) |
| UF, grandes regiões e país 2025 | `…/municipio_2025/Brasil/BR_{UF,Regioes,Pais}_2025.zip` | SHP zip (UF: 14 MB) | 27 UFs | geometria da UF |
| Regiões imediatas e intermediárias 2025 | `…/municipio_2025/Brasil/BR_RG_{Imediatas,Intermediarias}_2025.zip` | SHP zip | — | hierarquia regional |
| Recorte por UF 2025 | `…/municipio_2025/UFs/{UF}/{UF}_Municipios_2025.zip` | SHP zip (RS: 9,7 MB) | — | desenvolvimento e CI |
| Edições anteriores | `$GEOFTP/malhas_municipais/municipio_{2010,2013…2024}/` | SHP zip | 5.572 em 2015, 2019 e 2022 | série histórica |
| Setores censitários 2022 | `$GEOFTP/../malhas_de_setores_censitarios__divisoes_intramunicipais/censo_2022/setores/…` | GPKG 1,4 GB · SHP zip 738 MB | 468.099 | distrito, subdistrito, bairro, situação, favelas e comunidades urbanas |
| Bairros 2022 | `…/censo_2022/bairros/{gpkg,shp}/BR/BR_bairros_CD2022.*` | GPKG 53 MB · SHP zip 26 MB | 17.575 bairros em 895 municípios | bairro |
| Distritos e subdistritos 2022 | `…/censo_2022/{distritos,subdistritos}/{gpkg,shp}/{BR,UF}/` | GPKG · SHP zip ~240 MB cada | 10.699 distritos · 11.307 subdistritos | geometria de distrito |
| API Localidades | `$API/v1/localidades/{estados,municipios,distritos,…}?view=nivelado` | JSON | 27 · 5.571 · 10.751 · 646 · 510 · 133 | nomes, hierarquia, conferência de contagens |
| API Malhas v3 | `$API/v3/malhas/municipios/{id}?formato=application/vnd.geo+json&qualidade=…` | GeoJSON (SP: 1,3 KB na mínima, 25 KB na máxima) | — | referência de comparação, não fonte |

<details>
<summary>Colunas conferidas (todas em EPSG:4674, SIRGAS 2000)</summary>

- `BR_Municipios_2025`: `CD_MUN, NM_MUN, CD_RGI, NM_RGI, CD_RGINT, NM_RGINT, CD_UF, NM_UF, SIGLA_UF, CD_REGIAO, NM_REGIAO, SIGLA_RG, CD_CONCURB, NM_CONCURB, AREA_KM2`
- `BR_UF_2025`: `CD_UF, NM_UF, SIGLA_UF, CD_REGIAO, NM_REGIAO, SIGLA_RG, AREA_KM2`
- `BR_setores_CD2022`: `CD_SETOR, SITUACAO, CD_SIT, CD_TIPO, AREA_KM2, CD_REGIAO, NM_REGIAO, CD_UF, NM_UF, CD_MUN, NM_MUN, CD_DIST, NM_DIST, CD_SUBDIST, NM_SUBDIST, CD_BAIRRO, NM_BAIRRO, CD_NU, NM_NU, CD_FCU, NM_FCU, CD_AGLOM, NM_AGLOM, CD_RGINT, NM_RGINT, CD_RGI, NM_RGI, CD_CONCURB, NM_CONCURB`
- `BR_bairros_CD2022`: `CD_REGIAO, NM_REGIAO, CD_UF, NM_UF, CD_MUN, NM_MUN, CD_DIST, NM_DIST, CD_SUBDIST, NM_SUBDIST, CD_BAIRRO, NM_BAIRRO, CD_RGINT, NM_RGINT, CD_RGI, NM_RGI, CD_CONCURB, NM_CONCURB`

</details>

### O que os dados já ensinaram (vira regra ou teste)

1. **Nem toda feição é município.** A malha 2025 tem 5.573 feições para 5.571 municípios: entram `4300001 Área Operacional "Lagoa Mirim"` e `4300002 Área Operacional "Lagoa dos Patos"` (RS). → coluna `is_municipio`; o `reverse()` responde "área operacional" sem inventar município.
2. **A malha muda depois do Censo.** `5101837 Boa Esperança do Norte/MT` está na malha 2025, mas não na malha 2022 nem nos distritos 2022; distritos são 10.699 na malha 2022 e 10.751 na API hoje. Um ponto ali cai num setor 2022 de outro município. → o município sempre vem da malha vigente; camadas do Censo só complementam, e a divergência vira métrica.
3. **Bairro cobre pouco.** Só 895 municípios têm bairros na malha 2022 (Rio de Janeiro tem; São Paulo e Brasília não). Em São Paulo o nível útil é o distrito: são 96, ex.: `355030878 Sé`. → `bairro` pode ser nulo; distrito e subdistrito sempre vêm.
4. **Chave repetida no GPKG de bairros.** 18.269 feições para 17.575 `CD_BAIRRO` (o SHP tem uma feição por bairro). → agregar por código no staging; teste `unique`.
5. **O schema muda entre edições.** 2015: camada `BRMUE250GC_SIR` com `CD_GEOCMU, NM_MUNICIP`; 2019 e 2022: `CD_MUN, NM_MUN, SIGLA_UF, AREA_KM2`; 2025: 15 colunas com a hierarquia. → o staging padroniza por edição.
6. **Caminho e nome do arquivo também mudam.** `municipio_2015/Brasil/BR/br_municipios.zip`, `municipio_2019/Brasil/BR/br_municipios_20200807.zip`, `municipio_2025/Brasil/BR_Municipios_2025.zip`. → descobrir arquivos listando o diretório, com um manifesto de edições como plano B.
7. **Nome não é chave.** "Bom Jesus" existe em PI, RN, PB, SC e RS. → busca por nome sempre devolve a UF; a chave é `cd_mun` (7 dígitos, o último é verificador; o DATASUS usa os 6 primeiros).
8. **Área diverge entre fontes.** São Paulo: `AREA_KM2` = 1.522,683 na malha e 1.521,202 na API de metadados. → comparar áreas só com tolerância.
9. **Há polígonos gigantes.** Altamira/PA tem 159.533 km²: testar um ponto contra o polígono inteiro é caro. → `ST_Subdivide` (ver [Eficiência](#eficiência)).
10. **A cobertura do IBGE não é perfeita.** A malha 2025 tem 19 arestas inválidas (`ST_CoverageInvalidEdges`, frestas e sobreposições entre vizinhos) e a união por UF sai inválida em AC, PI e CE. → teste de cobertura como aviso; a simplificação não pode piorar a contagem; a geometria da UF passa por `ST_MakeValid`.
11. **As lagoas não têm distrito.** Nos setores 2022, os dois setores das lagoas Mirim e dos Patos (`430000100000000`, `430000200000000`) vêm sem `CD_MUN`, distrito ou subdistrito; nas malhas de distritos e subdistritos as duas lagoas são uma feição sem código. → `cd_mun` sai do `cd_setor`; a feição sem código sai do staging; o `not_null` de distrito ignora as áreas operacionais.
12. **Tabela nova não tem estatísticas.** Logo depois do build, `lkp_municipio` ainda não tem estatísticas: dentro do `dbt build`, a métrica de divergência não terminou em 9 min; com `analyze` no post-hook dos marts, 41 s (a mesma consulta isolada leva 23 s). → todo mart roda `analyze` ao final.

## Pipeline

### Orquestração (Airflow)

| DAG | Agenda | O que faz |
|---|---|---|
| `ibge_malha_municipal` | semanal (detecta edição nova) | descobre → baixa → valida → carrega `raw` → atualiza o asset |
| `ibge_localidades` | semanal | API Localidades → `raw` (JSONB) |
| `ibge_censo2022_intramunicipal` | manual (dado estático) | setores, bairros, distritos e subdistritos 2022 → `raw` |
| `dbt_geo` | por asset (quando um `raw` muda) | `dbt build` via Cosmos → PMTiles → publica a edição → smoke test |

```mermaid
flowchart LR
    a["descobrir edição<br/>lista o geoftp"] --> b{"já carregada?"}
    b -->|sim| fim(["fim"])
    b -->|não| c["baixar<br/>sha256 + retries"]
    c --> d["validar<br/>CRS, camadas, contagem"]
    d --> e["carregar raw<br/>ogr2ogr"]
    e --> f(["Asset raw.malha_municipal"])
    f --> g["dbt build<br/>Cosmos"]
    g --> h["gerar PMTiles"]
    h --> i["publicar edição<br/>meta.publicacao"]
    i --> j["smoke test<br/>pontos de referência"]
```

- **Idempotência:** repetir uma task não duplica nada. O download pula se o `sha256` já está no manifesto; a carga substitui só a edição em questão.
- **Bruto imutável:** os zips ficam em `data/raw/<fonte>/<edicao>/`; cada carga grava uma linha em `meta.cargas` (url, sha256, bytes, feições, duração).
- **Agendamento por dado:** assets do Airflow 3 ligam ingestão e transformação, sem sensores em loop.
- **Backfill:** disparo manual com `{"edicao": 2019}` carrega edições históricas.
- **Falha cedo:** CRS (EPSG:4674), camadas e contagem conferidos antes de tocar no banco.
- **Publicação explícita:** a biblioteca lê a edição registrada em `meta.publicacao`; publicar ou reverter é trocar esse valor, depois do smoke test.
- **Segredos fora do git:** conexões via `AIRFLOW_CONN_*` no `.env`.

### Ingestão (`raw`)

O GDAL lê o shapefile de dentro do zip (`/vsizip/`), sem extrair. Com `/vsicurl/` (ou `/vsizip//vsicurl/` para zip) lê direto da URL, baixando só os trechos necessários. Foi assim que as colunas e contagens acima foram conferidas.

```bash
# esboço: uma tabela por camada, com a edição marcada em cada linha
ogr2ogr -f PostgreSQL PG:"service=geo_loader" \
  /vsizip/data/raw/malha_municipal/2025/BR_Municipios_2025.zip \
  -dialect SQLITE -sql "SELECT *, 2025 AS _edicao FROM BR_Municipios_2025" \
  -nln raw.br_municipios -append -addfields \
  -nlt PROMOTE_TO_MULTI -lco GEOMETRY_NAME=geom
```

- `-addfields` acomoda colunas que aparecem em edições novas; nas antigas elas ficam nulas.
- Antes da carga, `DELETE … WHERE _edicao = 2025` (ou carga numa tabela temporária e troca numa transação).
- A API Localidades vira `raw.localidades_<nivel>`: uma linha JSONB por item, com a data da coleta.

### Transformação (dbt)

Schemas: `raw` → `staging` → `intermediate` → `marts`, mais `meta` (cargas e publicação) e `obs` (métricas de qualidade).

```text
models/
├── staging/                              # 1:1 com o raw: renomeia, tipa, padroniza
│   ├── stg_ibge__municipios.sql          # coalesce(cd_mun, cd_geocmu)… entre edições
│   ├── stg_ibge__ufs.sql
│   ├── stg_ibge__regioes.sql             # imediatas e intermediárias
│   ├── stg_ibge__setores_2022.sql
│   ├── stg_ibge__bairros_2022.sql        # agrega as feições por cd_bairro
│   └── stg_ibge__localidades.sql         # JSONB → colunas
├── intermediate/
│   ├── int_municipios__geom_valida.sql   # ST_MakeValid + ST_Multi
│   ├── int_municipios__simplificado.sql  # ST_CoverageSimplify em duas tolerâncias
│   ├── int_municipios__vizinhos.sql      # pares que fazem divisa (ST_Touches)
│   └── int_municipios__hierarquia.sql    # malha × Localidades
└── marts/
    ├── dim_municipio.sql   # sem geometria: códigos, nomes, nm_busca, hierarquia, bbox
    ├── geo_municipio.sql   # 3 resoluções + GeoJSON pré-serializado
    ├── geo_uf.sql
    ├── geo_bairro.sql
    ├── lkp_municipio.sql   # pedaços de ST_Subdivide; consultado pelo reverse()
    └── lkp_setor.sql       # setores 2022 subdivididos, com a hierarquia
```

Dois modelos centrais:

```sql
-- marts/lkp_municipio.sql: polígonos grandes viram pedaços de até 256 vértices
{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key='edicao',
    indexes=[{'columns': ['geom'], 'type': 'gist'}],
) }}

with pedacos as (
    select edicao, cd_mun, nm_mun, sg_uf, is_municipio,
           st_subdivide(geom, 256) as geom
    from {{ ref('int_municipios__geom_valida') }}
    where edicao = {{ var('edicao') }}
)
select * from pedacos
order by st_geohash(geom)  -- vizinhos no espaço ficam vizinhos no disco
```

```sql
-- intermediate/int_municipios__simplificado.sql: simplifica a cobertura toda
select edicao, cd_mun,
       geom                                                        as geom_alta,
       st_coveragesimplify(geom, 0.001) over (partition by edicao) as geom_media, -- ~100 m
       st_coveragesimplify(geom, 0.01)  over (partition by edicao) as geom_baixa  -- ~1 km
from {{ ref('int_municipios__geom_valida') }}
where edicao = {{ var('edicao') }}
```

- **Marts de serving são incrementais por edição** (`delete+insert` com `unique_key='edicao'`): a edição nova entra ao lado da publicada, sem trocar a tabela. Um `materialized='table'` no dbt-postgres renomeia a tabela antiga e a remove com `drop … cascade`, levando junto qualquer view que dependa dela.
- **Simplificação por edição, nunca por UF:** simplificar UF a UF abriria frestas nas divisas estaduais. As áreas operacionais entram na cobertura e só saem depois.
- Tolerâncias em graus (EPSG:4674), calibradas no notebook `02_simplificacao.py`.
- `geo_municipio` guarda `ST_AsGeoJSON(geom_*, 5)` pronto (5 casas ≈ 1 m); a biblioteca só converte.
- `nm_busca = lower(unaccent(nm_mun))` materializado, com índice trigram: `unaccent()` não é `IMMUTABLE`, então não dá para indexar a expressão direto.

### Qualidade

| Teste | Onde | Garante |
|---|---|---|
| `unique` + `not_null` em (`edicao`, `cd_mun`), `cd_setor`, `cd_bairro` | staging e marts | chaves |
| contagem por edição = municípios da API Localidades + 2 áreas operacionais | `dim_municipio` | completude |
| `ST_IsValid(geom)` e `ST_SRID(geom) = 4674` | todo modelo geo | geometria |
| `ST_CoverageInvalidEdges` vazio, antes e depois de simplificar (começa como `warn`) | `geo_municipio` | sem fresta ou sobreposição entre vizinhos |
| união dos municípios ≈ geometria da UF | `geo_uf` | coerência entre camadas |
| `ST_Area(geom::geography)` ≈ `AREA_KM2`, tolerância de 1% | staging | geometria íntegra |
| o `ST_PointOnSurface` de cada município cai nele mesmo | `lkp_municipio` | lookup correto |
| % de setores 2022 cujo ponto interno cai em outro município na malha vigente | `obs` (métrica, não falha) | divergência Censo × malha |
| pontos de referência em `seeds/pontos_referencia.csv` (ex.: Praça da Sé → `3550308`, distrito `355030878`) | smoke test depois do dbt | ponta a ponta |

## Serving

### Biblioteca Python (`geoibge`)

O uso final é Python: um pacote em `src/geoibge/` que lê os marts direto do PostGIS (papel `api_reader`) e devolve GeoDataFrames. Sem servidor HTTP no meio.

```python
import geoibge as gi

ufs = gi.ufs(["SP", "RJ", 31])                        # sigla ou código
mun = gi.municipios(["3550308", "330455", ("Bom Jesus", "PI")], resolucao="baixa")
sp  = gi.municipios(uf="SP")                           # todos da UF
hits = gi.buscar("bom jesus", uf="PI")                 # sem acento, tolerante a erro
pts = gi.reverse(df, lat="lat", lon="lon")             # um ponto, lista ou DataFrame

rel = gi.validar(mun)                                  # uma linha por feição
rel[~rel.ok]
```

| Função | Retorno |
|---|---|
| `ufs(ids=None)` | GeoDataFrame das UFs (todas, se `None`) |
| `municipios(ids=None, uf=None, resolucao="media")` | GeoDataFrame com atributos, hierarquia e bbox; aceita código de 6 ou 7 dígitos ou `(nome, uf)` |
| `buscar(texto, uf=None)` | candidatos por similaridade (trigram), com score |
| `vizinhos(codigo)` | municípios que fazem divisa |
| `reverse(pontos, lat=, lon=)` | hierarquia de cada ponto; aceita tupla, lista ou DataFrame |
| `validar(gdf)` | relatório por feição: `ST_IsValid` + motivo, SRID 4674, área × `AREA_KM2` (1%), vértices, tamanho do GeoJSON, `ok` |
| `edicoes()` | edições carregadas e a publicada |

- Todo parâmetro aceita `edicao=`; o padrão é a edição publicada em `meta.publicacao`.
- **Entrada inválida não some:** código inexistente, nome ambíguo ou sigla errada vira `ValueError` listando os itens problemáticos (ou linha com `erro` se `erros="marcar"`).
- **Validação rápida:** roda no banco, numa consulta só para a lista inteira (`unnest`), sem trazer geometria para o Python; `validar(..., cobertura=True)` acrescenta `ST_CoverageInvalidEdges` entre os itens.
- Conexão por `GEOIBGE_DSN` (ou `gi.conectar(dsn)`); pool do `psycopg` e leitura com `geopandas.read_postgis`.
- CLI fina para uso rápido: `uv run geoibge validar SP RJ 3550308`, `uv run geoibge mapa 3550308 -o sp.svg`.

### Desenho da UF com o município em destaque (sem banco)

A tarefa mais comum, código IBGE (ou CEP) → desenho da UF com o município marcado, não toca no banco: lê GeoJSON estático publicado em `src/geoibge/mapas/{cd_uf}.json` (27 arquivos, ~7,5 MB; MG, o maior, 770 KB). Os 2 primeiros dígitos do código dão a UF, então cada pedido abre um arquivo só.

```python
import geoibge as gi

fc = gi.mapa(3550308)                # FeatureCollection da UF; o pedido vem com properties.destaque = true
fc = gi.mapa(cep="01310-100")        # CEP → código pela ViaCEP (única parte com rede)
s  = gi.svg("355030", largura=800)   # SVG pronto; código de 6 dígitos também vale
```

| | |
|---|---|
| Arquivo | FeatureCollection compacta, UTF-8: 1ª feição é o contorno da UF (`nivel: "uf"`), depois uma por município (`nivel: "municipio"`, ou `"area_operacional"` nas lagoas do RS), com `id` = código, `nome` e `ponto` (ponto interno, para rótulo/marcador). Topo: `edicao`, `sg_uf`, `nm_uf`, `bbox`, `tolerancia`, `partes_omitidas` |
| Simplificação | `ST_CoverageSimplify` da malha média com tolerância da UF = lado maior / 1000 (≈ 1 px num desenho de 1000 px): DF e SE ficam detalhados, AM e PA não carregam vértice invisível. As divisas continuam encaixadas; casas decimais na medida da tolerância (3 ou 4) |
| Ilhas remotas | parte de município a mais de 2° do continente da UF sai do desenho (só Trindade e Martim Vaz, de Vitória, listadas em `partes_omitidas`); município todo oceânico fica (Fernando de Noronha) |
| Desempenho | `import geoibge` sem geopandas (imports preguiçosos); 1ª chamada da UF 5–40 ms (lê o JSON e projeta), seguintes < 0,5 ms (cache por UF) |
| SVG | equirretangular no paralelo central; municípios num `path` só, destaque e contorno por cima; município pequeno demais para ver ganha um círculo |

`make mapas` regera os arquivos depois de uma edição nova; `make mapa COD=3550308` (ou `CEP=…`) grava o SVG em `data/mapas/`. No GeoPandas: `gpd.GeoDataFrame.from_features(fc["features"], crs=4674)`.

#### `data/mapas.json`: os mesmos mapas sem Python

Arquivo único e versionado (~4,8 MB, ~1,7 MB com gzip) com tudo que o `svg()` usa, já projetado: qualquer linguagem monta o desenho só concatenando strings. Regerado por `make mapas-json`; um teste confere que está em dia e que segui-lo reproduz o `svg()` byte a byte.

| Chave | Conteúdo |
|---|---|
| `formato`, `edicao`, `fonte`, `projecao` | versão do formato (`geoibge-mapas/1`), edição da malha, origem e projeção |
| `lado_px`, `raio_marcador`, `cores` | escala do desenho (lado maior da UF), raio do círculo de destaque, paleta |
| `receita` | passo a passo para montar o SVG |
| `ufs.{cd_uf}` | `sigla`, `nome`, `largura`, `altura`, `contorno` (`d` do SVG) e `municipios` |
| `ufs.{cd_uf}.municipios.{cd_mun}` | `nome`, `nivel` (`municipio` ou `area_operacional`), `caixa` `[x0, y0, x1, y1]` e `d` |

```js
const cat = await (await fetch("mapas.json")).json();
function svg(cod) {
  const uf = cat.ufs[cod.slice(0, 2)], mun = uf.municipios[cod], c = cat.cores, m = cat.raio_marcador + 4;
  const ds = (n) => Object.values(uf.municipios).filter((x) => x.nivel === n).map((x) => x.d).join("");
  const [x0, y0, x1, y1] = mun.caixa, s = 'fill-rule="evenodd" vector-effect="non-scaling-stroke"';
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${-m} ${-m} ${uf.largura + 2 * m} ${uf.altura + 2 * m}">
    <path d="${ds("municipio")}" fill="${c.fundo}" stroke="${c.borda}" stroke-width="0.5" ${s}/>
    <path d="${ds("area_operacional")}" fill="${c.agua}" ${s}/>
    <path d="${mun.d}" fill="${c.destaque}" stroke="${c.destaque}" stroke-width="0.5" ${s}/>
    <path d="${uf.contorno}" fill="none" stroke="${c.uf}" stroke-width="1.2" ${s}/>
    ${Math.max(x1 - x0, y1 - y0) < cat.raio_marcador ? `<circle cx="${(x0 + x1) / 2}" cy="${(y0 + y1) / 2}"
      r="${cat.raio_marcador}" fill="none" stroke="${c.destaque}" stroke-width="2" ${s}/>` : ""}</svg>`;
}
document.body.innerHTML = svg("3550308");
```

Para geometria em lon/lat (GIS, Leaflet), use os GeoJSON de `src/geoibge/mapas/`.

Resultado de `reverse()` para um ponto (colunas do DataFrame, mostradas como dict):

```json
{
  "ponto": {"lat": -23.5503, "lon": -46.6339},
  "uf": {"codigo": "35", "sigla": "SP", "nome": "São Paulo"},
  "municipio": {"codigo": "3550308", "nome": "São Paulo", "edicao": 2025},
  "regiao_imediata": {"codigo": "350001", "nome": "São Paulo"},
  "regiao_intermediaria": {"codigo": "3501", "nome": "São Paulo"},
  "distrito": {"codigo": "355030878", "nome": "Sé", "edicao": 2022},
  "bairro": null,
  "setor": {"codigo": "…", "situacao": "urbana", "edicao": 2022},
  "avisos": ["município sem malha de bairros; distrito informado"]
}
```

```sql
-- núcleo do reverse(); ST_MakePoint recebe (x, y) = (lon, lat)
with p as (
    select st_setsrid(st_makepoint(:lon, :lat), 4674) as geom
)
select m.cd_mun, m.nm_mun, m.sg_uf, m.is_municipio,
       s.cd_setor, s.situacao, s.cd_dist, s.nm_dist,
       s.cd_subdist, s.nm_subdist, s.cd_bairro, s.nm_bairro
from p
left join lateral (
    select l.cd_mun, l.nm_mun, l.sg_uf, l.is_municipio
    from marts.lkp_municipio l
    where l.edicao = :edicao and st_intersects(l.geom, p.geom)
    order by l.cd_mun  -- ponto exatamente na divisa: desempate determinístico
    limit 1
) m on true
left join lateral (
    select l.cd_setor, l.situacao, l.cd_dist, l.nm_dist,
           l.cd_subdist, l.nm_subdist, l.cd_bairro, l.nm_bairro
    from marts.lkp_setor l
    where st_intersects(l.geom, p.geom)
    limit 1
) s on true;
```

- **Lote:** o mesmo SQL com `from unnest(:ids, :lons, :lats) as t(id, lon, lat)` no lugar do ponto único: uma ida ao banco para milhares de pontos.
- **Ponto na costa, fora da malha:** fallback para o município mais próximo (`order by geom <-> p.geom`) até 1 km, com aviso.
- **Fora do Brasil:** linha com `erro="fora_do_brasil"` depois de um filtro barato pelo bbox nacional.

### Mapas

- **Martin** publica `geo_municipio`, `geo_uf` e `geo_bairro` como vector tiles direto do PostGIS: bom para desenvolvimento.
- **PMTiles por edição:** PostGIS → FlatGeobuf (`ogr2ogr`) → `tippecanoe` → um `.pmtiles` com municípios, UFs e bairros (bairros só em zoom alto). Arquivo único e estático, servido pelo Martin sem tocar no banco.
- **Notebook `05_explorador.py`** com lonboard: `geoibge.municipios()` → mapa; clique → `geoibge.reverse()`. Martin fica para abrir as camadas no QGIS.

### Eficiência

| Técnica | Problema que resolve |
|---|---|
| `ST_Subdivide(geom, 256)` + índice GiST na tabela de lookup | o bbox de um polígono gigante "acerta" muitos pontos e o teste exato percorre milhares de vértices; pedaços pequenos têm bbox justo e teste barato |
| `ST_CoverageSimplify` sobre a cobertura nacional | simplificar município a município abre frestas e sobreposições entre vizinhos; a simplificação de cobertura preserva as divisas compartilhadas |
| Três resoluções e GeoJSON pré-calculados | nada de simplificar ou serializar por requisição |
| PMTiles por edição | o mapa não toca no banco; um arquivo estático e cacheável |
| Cache local por edição (`functools.cache` + GeoParquet em `~/.cache/geoibge/`) | o dado muda uma vez por ano; consultas repetidas não tocam no banco |
| Lote com `unnest` + `LATERAL` | uma ida ao banco para milhares de pontos |
| Ordem espacial na materialização (`order by st_geohash(geom)`) | pontos próximos leem as mesmas páginas do disco |
| Experimento: H3 pré-computado (`h3-pg`) | células inteiras dentro de um município viram busca por chave; só as de borda fazem point-in-polygon |

## Observabilidade (Grafana)

Coleta:

- **Airflow** → StatsD (`AIRFLOW__METRICS__STATSD_ON=True`) → `statsd-exporter` → Prometheus: duração e status dos DAG runs, falhas de task, erros de import, heartbeat do scheduler.
- **PostgreSQL** → `postgres-exporter` + `pg_stat_statements`: conexões, cache hit, consultas lentas.
- **Qualidade** → `meta.cargas`, `obs.*` e `marts.*`, lidas direto pelo datasource PostgreSQL do Grafana (papel `monitor`). Elementary ainda não integrado.

Dashboards, provisionados como código em `infra/grafana/`:

1. **Pipeline:** última edição carregada e publicada, duração e status por DAG e task.
2. **Qualidade:** testes do dbt por execução, contagens por edição × API Localidades, geometrias inválidas, divergência setores 2022 × malha vigente.
3. **Banco:** conexões, cache hit ratio, consultas mais caras.
4. **Consultas da biblioteca:** latência das consultas de `reverse()` e `validar()` via `pg_stat_statements`.

Implementado em `infra/`: `prometheus/prometheus.yml`, `statsd/mapping.yml` (dag_id/task_id/state viram labels), `grafana/provisioning/` (datasources `prometheus` e `geo-pg`) e `grafana/dashboards/*.json`. O papel `monitor` (`pg_monitor` + leitura de `meta`, `obs`, `marts`) é criado por `infra/postgres/init/02_monitor.sh`, que o `make obs` reaplica em volumes antigos.

Alertas (pendente): DAG falhou; teste do dbt com `error`; edição nova detectada (informativo).

## Notebooks (marimo)

Arquivos `.py` em `notebooks/`, abertos com `uv run marimo edit notebooks/<arquivo>.py`. Mapas com lonboard (deck.gl, aguenta milhares de polígonos).

| Notebook | Conteúdo |
|---|---|
| `01_explorar_fontes.py` | lê os zips com GeoPandas/pyogrio: CRS, colunas, contagens, vértices por município, mapa |
| `02_simplificacao.py` | slider de tolerância → tamanho do GeoJSON × fidelidade; simplificação ingênua (frestas) × `ST_CoverageSimplify` |
| `03_benchmark_reverse.py` | 100 mil pontos aleatórios: polígono inteiro × `ST_Subdivide` × H3; latência e `EXPLAIN ANALYZE` |
| `04_qa_edicao.py` | diff entre edições: municípios novos, removidos e com limite alterado (`ST_SymDifference`) |
| `05_explorador.py` | app (`marimo run`): UF → município → mapa; clique → `geoibge.reverse()` |
| `06_tour.py` | exemplo final: edições e cargas, `ufs()`, `municipios()`, `reverse()` em lote, mapa, `validar()` e links dos dashboards |

## Ambiente local (Docker Compose)

| Serviço | Imagem | Porta | Profile |
|---|---|---|---|
| `postgis` | `postgis/postgis:18-3.6` | 5432 | sempre |
| `martin` | `ghcr.io/maplibre/martin` | 3001 | `core` |
| `airflow-init`, `airflow-apiserver`, `airflow-scheduler`, `airflow-dag-processor`, `airflow-triggerer` | build `./airflow` | 8080 (api-server) | `airflow` |
| `prometheus` | `prom/prometheus` | 9090 | `obs` |
| `grafana` | `grafana/grafana` | 3000 | `obs` |
| `statsd-exporter` | `prom/statsd-exporter` | 9102 | `obs` |
| `postgres-exporter` | `prometheuscommunity/postgres-exporter` | 9187 | `obs` |
| `marimo` | build `./notebooks` (opcional; dá para rodar com `uv` fora do Docker) | 2718 | `dev` |

- Um PostgreSQL, dois bancos: `airflow` (metadados) e `geo` (dados). Papéis: `loader` escreve no `raw`; `transformer` (dbt) lê o `raw` e escreve nas camadas seguintes; `api_reader` (biblioteca) só lê `marts` e `meta`.
- Extensões no `geo`: `postgis`, `pg_trgm`, `unaccent`, `pg_stat_statements` (exige `shared_preload_libraries`).
- A imagem do Airflow leva GDAL (`ogr2ogr`), tippecanoe e o dbt num virtualenv próprio, como o Cosmos recomenda.
- O Martin escuta na 3000 por padrão, a mesma porta do Grafana: mapear para 3001.

Uso pretendido:

```bash
cp .env.example .env
docker compose --profile core --profile airflow up -d   # banco, tiles e Airflow
docker compose --profile obs up -d                       # Prometheus e Grafana
uv run marimo edit notebooks/01_explorar_fontes.py
uv run python -c 'import geoibge as gi; print(gi.validar(gi.ufs(["SP"])))'
```

## Estrutura do repositório

```text
geo/
├── README.md
├── docker-compose.yml
├── .env.example
├── Makefile                      # comandos do projeto (make help)
├── scripts/status.py             # painel do make status (rich)
├── pyproject.toml                # uv: geoibge, marimo, geopandas, psycopg, lonboard
├── airflow/
│   ├── Dockerfile                # Airflow + GDAL + tippecanoe + venv do dbt
│   ├── dags/                     # as 4 DAGs (ibge_*, dbt_geo)
│   └── include/ibge/             # listagem do geoftp, download com checksum, validação
├── dbt/
│   ├── dbt_project.yml
│   ├── profiles.yml
│   ├── packages.yml              # dbt_utils, elementary
│   ├── seeds/                    # manifesto de edições, pontos de referência
│   ├── macros/                   # testes genéricos espaciais
│   └── models/{staging,intermediate,marts}/
├── src/geoibge/                  # biblioteca e CLI
│   └── mapas/                    # GeoJSON por UF para o desenho (make mapas)
├── data/mapas.json               # paths SVG prontos por UF, para uso externo (make mapas-json); resto de data/ fora do git
├── tests/
├── tiles/martin.yaml
├── notebooks/
├── infra/
│   ├── postgres/init/            # bancos, extensões, papéis
│   ├── prometheus/prometheus.yml
│   ├── statsd/mapping.yml
│   └── grafana/provisioning/     # datasources e dashboards
└── data/                         # fora do git: raw/ e tiles/
```

## Roadmap

**Fase 0 — Fundação**
- [x] `docker-compose.yml` com `postgis` e init (bancos, extensões, papéis); `.gitignore` com `data/` e `.env`
- [x] `pyproject.toml` (uv) e `01_explorar_fontes.py` com a malha de uma UF

**Fase 1 — Ingestão**
- [x] Airflow no compose (LocalExecutor)
- [x] DAG `ibge_malha_municipal`: descoberta, download com checksum, validação, `ogr2ogr` → `raw`
- [x] `meta.cargas` e backfill das edições históricas (edições com zip nacional; 2010, 2013 e 2014 só têm recorte por UF)
- [x] DAG `ibge_localidades`

**Fase 2 — Transformação**
- [x] dbt: staging e marts de município e UF (`dim_municipio`, `geo_municipio`, `geo_uf`)
- [x] Testes de chave, geometria, contagem e cobertura
- [x] Cosmos + asset ligando ingestão → dbt (`dbt_geo`)

**Fase 3 — Serving**
- [x] `geoibge`: `ufs()`, `municipios()`, `validar()` e `reverse()` (até município), sobre `lkp_municipio` e `meta.publicacao`
- [x] Martin + `05_explorador.py`
- [x] `02_simplificacao.py` e `03_benchmark_reverse.py` para calibrar resoluções e validar as metas

  Medido em 30/10/2026 (malha 2025, local): `reverse()` p95 4,5 ms; lote de 100 mil pontos em 2,8 s; `municipios()` de um código p95 5 ms; validação de MG (853) em 1,7 s. Tolerâncias mantidas: no RJ, 0,001° reduz o GeoJSON de 8,9 MB para 649 KB (desvio máx. 0,3 km) e 0,01° para 121 KB (3,2 km), sem fresta; a simplificação ingênua abre 90 arestas inválidas.

**Fase 4 — Intramunicipal**
- [x] DAG do Censo 2022: setores, bairros, distritos e subdistritos
- [x] `lkp_setor` e `reverse()` completo
- [x] Métrica de divergência setores 2022 × malha vigente

  Medido em 30/10/2026: carga das quatro camadas em ~1 min (setores: 468.099 em 35 s); `lkp_setor` com 879.109 pedaços; `reverse()` com setor, distrito e bairro p95 5,9 ms, lote de 100 mil em 7,2 s. Divergência: 208 setores (0,044%) caem em outro município na malha 2025 (191 na 2019), ex.: 10 setores de Nova Ubiratã/MT em `5101837 Boa Esperança do Norte`, criado depois do Censo. Martin publica `bairros` (zoom ≥ 10) e `distritos` (zoom ≥ 8).

**Fase 5 — Observabilidade**
- [x] Prometheus, exporters e Grafana provisionado
- [x] Dashboards Pipeline, Qualidade e Banco
- [ ] Alertas e integração com elementary

**Fase 6 — Extras**
- [ ] PMTiles por edição no pipeline
- [ ] Cache local por edição e `reverse()` em lote grande (COPY + tabela temporária)
- [ ] CI (GitHub Actions): `dbt build` com o recorte de uma UF pequena, testes da biblioteca, carga das DAGs sem erro de import
- [ ] Experimentos: H3, saída em GeoParquet para DuckDB, CNEFE 2022 (endereços) para reverse no nível da rua, bairros do OpenStreetMap onde o IBGE não tem

## Decisões e cuidados

- **PostGIS como warehouse e serving.** Um banco só simplifica o estudo, e é nele que estão GiST, `ST_Subdivide`, as funções de cobertura e a integração com Martin e dbt-postgres. DuckDB fica para análise ad hoc nos notebooks.
- **Por que não usar só a API de Malhas do IBGE?** Ela entrega a geometria por código, mas não responde "ponto → município", e chamá-la a cada requisição põe a latência e a disponibilidade de terceiros no caminho. Fica como referência de comparação.
- **GEOS ≥ 3.12 para `ST_Coverage*`.** A imagem `postgis/postgis:18-3.6` é baseada em Debian trixie (GEOS 3.13); o Debian bookworm tem GEOS 3.11, sem essas funções. Conferir com `SELECT postgis_full_version();`.
- **Ordem `lon, lat`.** `ST_MakePoint(x, y)` é `(lon, lat)`; a biblioteca recebe `lat` e `lon` nomeados para evitar troca.
- **WGS84 × SIRGAS 2000.** GPS entrega WGS84 (EPSG:4326) e a malha está em SIRGAS 2000 (EPSG:4674); a diferença é desprezível na escala da malha, então o ponto entra como 4674 (`ST_SetSRID`), sem reprojetar.
- **Precisão.** A malha municipal é compatível com a escala 1:250.000: perto de uma divisa, o ponto pode cair no vizinho. Documentar na biblioteca e avisar quando o ponto estiver a poucas centenas de metros da divisa.
- **Edição em tudo.** `edicao` faz parte da chave de todo modelo; consultas históricas passam `edicao=`.
- **Biblioteca em vez de API HTTP.** O consumo é Python (notebooks e scripts); um FastAPI só acrescentaria serialização, deploy e latência. Se surgir outro consumidor, a API vira uma casca fina sobre `geoibge`.
- **Atribuição.** Dados públicos do IBGE; citar a fonte nos resultados e nos mapas.

## Referências

- [Malhas territoriais do IBGE (geoftp)](https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/)
- [API de Localidades](https://servicodados.ibge.gov.br/api/docs/localidades) · [API de Malhas v3](https://servicodados.ibge.gov.br/api/docs/malhas?versao=3)
- PostGIS: [`ST_Subdivide`](https://postgis.net/docs/ST_Subdivide.html) · [`ST_CoverageSimplify`](https://postgis.net/docs/ST_CoverageSimplify.html) · [`ST_CoverageInvalidEdges`](https://postgis.net/docs/ST_CoverageInvalidEdges.html)
- [Airflow](https://airflow.apache.org/docs/apache-airflow/stable/) · [Cosmos](https://astronomer.github.io/astronomer-cosmos/) · [configs do dbt-postgres (índices)](https://docs.getdbt.com/reference/resource-configs/postgres-configs) · [elementary](https://docs.elementary-data.com/)
- [marimo](https://docs.marimo.io/) · [lonboard](https://github.com/developmentseed/lonboard)
- [Martin](https://maplibre.org/martin/) · [PMTiles](https://docs.protomaps.com/pmtiles/) · [tippecanoe](https://github.com/felt/tippecanoe)
- [geobr (IPEA)](https://github.com/ipeaGIT/geobr): malhas do IBGE harmonizadas entre edições; boa referência de comparação
