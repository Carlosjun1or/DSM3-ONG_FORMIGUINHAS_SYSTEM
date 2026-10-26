"""
Migration que cria fisicamente as tabelas bag e movimentacao_bag.
Compatível com SQLite e PostgreSQL.
"""
from django.db import migrations

SQLITE = {
    'bag': """
CREATE TABLE IF NOT EXISTS bag (
    id_bag                   INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo                   VARCHAR(40)    NOT NULL UNIQUE,
    status                   VARCHAR(20)    NOT NULL DEFAULT 'DISPONIVEL',
    peso_atual_kg            DECIMAL(7,2)   NOT NULL DEFAULT 0,
    percentual_ocupacao      SMALLINT       NOT NULL DEFAULT 0,
    observacoes              TEXT           NOT NULL DEFAULT '',
    dt_cadastro              DATETIME       NOT NULL,
    cadastrado_por_id        INTEGER        REFERENCES usuario(id_usuario) ON DELETE SET NULL,
    cadastrado_por_nome      VARCHAR(150)   NOT NULL DEFAULT '',
    dt_ultima_edicao         DATETIME,
    ultimo_editado_por_id    INTEGER        REFERENCES usuario(id_usuario) ON DELETE SET NULL,
    ultimo_editado_por_nome  VARCHAR(150)   NOT NULL DEFAULT '',
    condominio_id            INTEGER        NOT NULL REFERENCES condominio(id_condominio) ON DELETE RESTRICT
)""",
    'movimentacao_bag': """
CREATE TABLE IF NOT EXISTS movimentacao_bag (
    id_movimentacao   INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo              VARCHAR(30)  NOT NULL,
    status_anterior   VARCHAR(20)  NOT NULL,
    status_novo       VARCHAR(20)  NOT NULL,
    data_movimentacao DATETIME     NOT NULL,
    observacao        TEXT         NOT NULL DEFAULT '',
    registrado_por_nome VARCHAR(150) NOT NULL,
    dt_cadastro       DATETIME     NOT NULL,
    bag_id            INTEGER      NOT NULL REFERENCES bag(id_bag) ON DELETE RESTRICT,
    registrado_por_id INTEGER      NOT NULL REFERENCES usuario(id_usuario) ON DELETE RESTRICT
)""",
}

POSTGRES = {
    'bag': """
CREATE TABLE IF NOT EXISTS bag (
    id_bag                   SERIAL PRIMARY KEY,
    codigo                   VARCHAR(40)    NOT NULL UNIQUE,
    status                   VARCHAR(20)    NOT NULL DEFAULT 'DISPONIVEL',
    peso_atual_kg            DECIMAL(7,2)   NOT NULL DEFAULT 0,
    percentual_ocupacao      SMALLINT       NOT NULL DEFAULT 0,
    observacoes              TEXT           NOT NULL DEFAULT '',
    dt_cadastro              TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    cadastrado_por_id        INTEGER        REFERENCES usuario(id_usuario) ON DELETE SET NULL,
    cadastrado_por_nome      VARCHAR(150)   NOT NULL DEFAULT '',
    dt_ultima_edicao         TIMESTAMPTZ,
    ultimo_editado_por_id    INTEGER        REFERENCES usuario(id_usuario) ON DELETE SET NULL,
    ultimo_editado_por_nome  VARCHAR(150)   NOT NULL DEFAULT '',
    condominio_id            INTEGER        NOT NULL REFERENCES condominio(id_condominio) ON DELETE RESTRICT
)""",
    'movimentacao_bag': """
CREATE TABLE IF NOT EXISTS movimentacao_bag (
    id_movimentacao   SERIAL PRIMARY KEY,
    tipo              VARCHAR(30)  NOT NULL,
    status_anterior   VARCHAR(20)  NOT NULL,
    status_novo       VARCHAR(20)  NOT NULL,
    data_movimentacao TIMESTAMPTZ  NOT NULL,
    observacao        TEXT         NOT NULL DEFAULT '',
    registrado_por_nome VARCHAR(150) NOT NULL,
    dt_cadastro       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    bag_id            INTEGER      NOT NULL REFERENCES bag(id_bag) ON DELETE RESTRICT,
    registrado_por_id INTEGER      NOT NULL REFERENCES usuario(id_usuario) ON DELETE RESTRICT
)""",
}


def _criar(apps, schema_editor):
    sqls = POSTGRES if schema_editor.connection.vendor == 'postgresql' else SQLITE
    for sql in sqls.values():
        schema_editor.execute(sql)


def _reverter(apps, schema_editor):
    schema_editor.execute('DROP TABLE IF EXISTS movimentacao_bag')
    schema_editor.execute('DROP TABLE IF EXISTS bag')


class Migration(migrations.Migration):

    dependencies = [
        ('condominio', '0005_criar_tabela_condominio_sql'),
        ('usuario', '0002_audit_snapshots'),
    ]

    operations = [
        migrations.RunPython(_criar, reverse_code=_reverter),
    ]
