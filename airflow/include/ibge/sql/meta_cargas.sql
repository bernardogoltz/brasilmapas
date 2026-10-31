-- Uma linha por carga em raw (malha ou API). Criada pelo loader na primeira execução.
CREATE TABLE IF NOT EXISTS meta.cargas (
    id            bigserial PRIMARY KEY,
    fonte         text        NOT NULL,
    edicao        int,
    url           text        NOT NULL,
    sha256        text,
    bytes         bigint,
    feicoes       int,
    duracao_s     numeric(10, 2),
    carregado_em  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS cargas_fonte_edicao ON meta.cargas (fonte, edicao);
