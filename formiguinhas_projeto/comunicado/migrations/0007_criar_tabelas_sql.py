"""
Migration que cria fisicamente as tabelas do app 'comunicado'.
Compatível com SQLite e PostgreSQL.
"""
from django.db import migrations

SQLITE = {
    'comunicado_tema': """
CREATE TABLE IF NOT EXISTS comunicado_tema (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    nome              VARCHAR(120) NOT NULL UNIQUE,
    descricao         TEXT         NOT NULL DEFAULT '',
    ativo             BOOLEAN      NOT NULL DEFAULT 1,
    criado_por_id     INTEGER,
    atualizado_por_id INTEGER,
    criado_em         DATETIME     NOT NULL,
    atualizado_em     DATETIME     NOT NULL
)""",
    'comunicado': """
CREATE TABLE IF NOT EXISTS comunicado (
    id_comunicado             INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo                      VARCHAR(10)  NOT NULL,
    titulo                    VARCHAR(200) NOT NULL,
    resumo                    VARCHAR(500) NOT NULL DEFAULT '',
    conteudo                  TEXT         NOT NULL,
    publico                   VARCHAR(15)  NOT NULL DEFAULT 'TODOS',
    status                    VARCHAR(12)  NOT NULL DEFAULT 'RASCUNHO',
    tema_id                   INTEGER      REFERENCES comunicado_tema(id) ON DELETE RESTRICT,
    dt_publicacao             DATETIME,
    dt_expiracao              DATETIME,
    duracao_expiracao         INTEGER,
    unidade_duracao_expiracao VARCHAR(10),
    autor_id                  INTEGER,
    perfil_autor              VARCHAR(20)  NOT NULL DEFAULT '',
    ultimo_editado_por_id     INTEGER,
    dt_ultima_edicao          DATETIME,
    criado_em                 DATETIME     NOT NULL,
    atualizado_em             DATETIME     NOT NULL
)""",
    'comunicado_praia': """
CREATE TABLE IF NOT EXISTS comunicado_praia (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    comunicado_id INTEGER NOT NULL REFERENCES comunicado(id_comunicado) ON DELETE CASCADE,
    praia_id      INTEGER NOT NULL,
    UNIQUE (comunicado_id, praia_id)
)""",
    'comunicado_equipe': """
CREATE TABLE IF NOT EXISTS comunicado_equipe (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    comunicado_id INTEGER NOT NULL REFERENCES comunicado(id_comunicado) ON DELETE CASCADE,
    equipe_id     INTEGER NOT NULL,
    UNIQUE (comunicado_id, equipe_id)
)""",
    'comunicado_acao': """
CREATE TABLE IF NOT EXISTS comunicado_acao (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    comunicado_id INTEGER NOT NULL REFERENCES comunicado(id_comunicado) ON DELETE CASCADE,
    acao_id       INTEGER NOT NULL,
    UNIQUE (comunicado_id, acao_id)
)""",
    'comunicado_doacao': """
CREATE TABLE IF NOT EXISTS comunicado_doacao (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    comunicado_id INTEGER NOT NULL REFERENCES comunicado(id_comunicado) ON DELETE CASCADE,
    doacao_id     INTEGER NOT NULL,
    UNIQUE (comunicado_id, doacao_id)
)""",
    'comunicado_leitura': """
CREATE TABLE IF NOT EXISTS comunicado_leitura (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    comunicado_id INTEGER NOT NULL REFERENCES comunicado(id_comunicado) ON DELETE CASCADE,
    usuario_id    INTEGER NOT NULL,
    lido_em       DATETIME NOT NULL,
    UNIQUE (comunicado_id, usuario_id)
)""",
}

POSTGRES = {
    'comunicado_tema': """
CREATE TABLE IF NOT EXISTS comunicado_tema (
    id                SERIAL PRIMARY KEY,
    nome              VARCHAR(120) NOT NULL UNIQUE,
    descricao         TEXT         NOT NULL DEFAULT '',
    ativo             BOOLEAN      NOT NULL DEFAULT TRUE,
    criado_por_id     INTEGER,
    atualizado_por_id INTEGER,
    criado_em         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    atualizado_em     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
)""",
    'comunicado': """
CREATE TABLE IF NOT EXISTS comunicado (
    id_comunicado             SERIAL PRIMARY KEY,
    tipo                      VARCHAR(10)  NOT NULL,
    titulo                    VARCHAR(200) NOT NULL,
    resumo                    VARCHAR(500) NOT NULL DEFAULT '',
    conteudo                  TEXT         NOT NULL,
    publico                   VARCHAR(15)  NOT NULL DEFAULT 'TODOS',
    status                    VARCHAR(12)  NOT NULL DEFAULT 'RASCUNHO',
    tema_id                   INTEGER      REFERENCES comunicado_tema(id) ON DELETE RESTRICT,
    dt_publicacao             TIMESTAMPTZ,
    dt_expiracao              TIMESTAMPTZ,
    duracao_expiracao         INTEGER,
    unidade_duracao_expiracao VARCHAR(10),
    autor_id                  INTEGER,
    perfil_autor              VARCHAR(20)  NOT NULL DEFAULT '',
    ultimo_editado_por_id     INTEGER,
    dt_ultima_edicao          TIMESTAMPTZ,
    criado_em                 TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    atualizado_em             TIMESTAMPTZ  NOT NULL DEFAULT NOW()
)""",
    'comunicado_praia': """
CREATE TABLE IF NOT EXISTS comunicado_praia (
    id            SERIAL PRIMARY KEY,
    comunicado_id INTEGER NOT NULL REFERENCES comunicado(id_comunicado) ON DELETE CASCADE,
    praia_id      INTEGER NOT NULL,
    UNIQUE (comunicado_id, praia_id)
)""",
    'comunicado_equipe': """
CREATE TABLE IF NOT EXISTS comunicado_equipe (
    id            SERIAL PRIMARY KEY,
    comunicado_id INTEGER NOT NULL REFERENCES comunicado(id_comunicado) ON DELETE CASCADE,
    equipe_id     INTEGER NOT NULL,
    UNIQUE (comunicado_id, equipe_id)
)""",
    'comunicado_acao': """
CREATE TABLE IF NOT EXISTS comunicado_acao (
    id            SERIAL PRIMARY KEY,
    comunicado_id INTEGER NOT NULL REFERENCES comunicado(id_comunicado) ON DELETE CASCADE,
    acao_id       INTEGER NOT NULL,
    UNIQUE (comunicado_id, acao_id)
)""",
    'comunicado_doacao': """
CREATE TABLE IF NOT EXISTS comunicado_doacao (
    id            SERIAL PRIMARY KEY,
    comunicado_id INTEGER NOT NULL REFERENCES comunicado(id_comunicado) ON DELETE CASCADE,
    doacao_id     INTEGER NOT NULL,
    UNIQUE (comunicado_id, doacao_id)
)""",
    'comunicado_leitura': """
CREATE TABLE IF NOT EXISTS comunicado_leitura (
    id            SERIAL PRIMARY KEY,
    comunicado_id INTEGER NOT NULL REFERENCES comunicado(id_comunicado) ON DELETE CASCADE,
    usuario_id    INTEGER NOT NULL,
    lido_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (comunicado_id, usuario_id)
)""",
}

IDX1 = "CREATE INDEX IF NOT EXISTS comunicado_status_553339_idx ON comunicado (status, publico, dt_publicacao)"
IDX2 = "CREATE INDEX IF NOT EXISTS comunicado_tipo_2cfb9c_idx ON comunicado (tipo, status)"
IDX_LEITURA = "CREATE INDEX IF NOT EXISTS comunicado__usuario_bee43b_idx ON comunicado_leitura (usuario_id, lido_em)"


def _criar(apps, schema_editor):
    sqls = POSTGRES if schema_editor.connection.vendor == 'postgresql' else SQLITE
    for sql in sqls.values():
        schema_editor.execute(sql)
    schema_editor.execute(IDX1)
    schema_editor.execute(IDX2)
    schema_editor.execute(IDX_LEITURA)


def _reverter(apps, schema_editor):
    schema_editor.execute('DROP INDEX IF EXISTS comunicado__usuario_bee43b_idx')
    schema_editor.execute('DROP INDEX IF EXISTS comunicado_tipo_2cfb9c_idx')
    schema_editor.execute('DROP INDEX IF EXISTS comunicado_status_553339_idx')
    for t in reversed(['comunicado_leitura', 'comunicado_doacao', 'comunicado_acao',
                       'comunicado_equipe', 'comunicado_praia', 'comunicado', 'comunicado_tema']):
        schema_editor.execute(f'DROP TABLE IF EXISTS {t}')


class Migration(migrations.Migration):

    dependencies = [
        ('comunicado', '0006_alter_comunicado_options_and_more'),
        ('usuario', '0002_audit_snapshots'),
        ('praia', '0003_praia_cadastrado_por_praia_dt_cadastro'),
        ('equipe', '0002_equipe_praia'),
        ('acao', '0002_criar_tabelas_sql'),
        ('doacao', '0002_doador_doador_documento_unico_nao_vazio_and_more'),
    ]

    operations = [
        migrations.RunPython(_criar, reverse_code=_reverter),
    ]
