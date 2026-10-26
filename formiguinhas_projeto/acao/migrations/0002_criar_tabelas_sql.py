"""
Migration que cria fisicamente as tabelas do app 'acao'.
Compatível com SQLite e PostgreSQL.
"""
from django.db import migrations

SQLITE = {
    'acao': """
CREATE TABLE IF NOT EXISTS acao (
    id_acao       INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo          VARCHAR(30)   NOT NULL,
    data          DATE          NOT NULL,
    horario       TIME,
    local         VARCHAR(255)  NOT NULL DEFAULT '',
    descricao     TEXT          NOT NULL DEFAULT '',
    status        VARCHAR(20)   NOT NULL DEFAULT 'PLANEJADA',
    imagens       JSON          NOT NULL DEFAULT '[]',
    praia_id      INTEGER,
    dt_cadastro   DATETIME      NOT NULL,
    cadastrado_por_id      INTEGER,
    cadastrado_por_nome    VARCHAR(150),
    cadastrado_por_tipo    VARCHAR(20),
    dt_ultima_edicao       DATETIME,
    ultimo_editado_por_id  INTEGER,
    ultimo_editado_por_nome VARCHAR(150),
    ultimo_editado_por_tipo VARCHAR(20)
)""",
    'acao_imagem': """
CREATE TABLE IF NOT EXISTS acao_imagem (
    id_acao_imagem INTEGER PRIMARY KEY AUTOINCREMENT,
    acao_id        INTEGER  NOT NULL REFERENCES acao(id_acao) ON DELETE CASCADE,
    imagem         VARCHAR(100) NOT NULL,
    descricao      VARCHAR(255) NOT NULL DEFAULT '',
    dt_cadastro    DATETIME     NOT NULL
)""",
    'acao_equipe': """
CREATE TABLE IF NOT EXISTS acao_equipe (
    id_acao_equipe INTEGER PRIMARY KEY AUTOINCREMENT,
    acao_id        INTEGER NOT NULL REFERENCES acao(id_acao) ON DELETE CASCADE,
    equipe_id      INTEGER NOT NULL,
    UNIQUE (acao_id, equipe_id)
)""",
    'acao_participante': """
CREATE TABLE IF NOT EXISTS acao_participante (
    id_acao_participante INTEGER PRIMARY KEY AUTOINCREMENT,
    acao_id        INTEGER  NOT NULL REFERENCES acao(id_acao) ON DELETE CASCADE,
    voluntario_id  INTEGER  NOT NULL,
    status         VARCHAR(20)  NOT NULL DEFAULT 'PENDENTE',
    compareceu     BOOLEAN      NOT NULL DEFAULT 0,
    observacao     TEXT         NOT NULL DEFAULT '',
    dt_confirmacao DATETIME,
    dt_cadastro    DATETIME     NOT NULL,
    UNIQUE (acao_id, voluntario_id)
)""",
    'acao_participante_historico': """
CREATE TABLE IF NOT EXISTS acao_participante_historico (
    id_historico   INTEGER PRIMARY KEY AUTOINCREMENT,
    acao_id        INTEGER  NOT NULL REFERENCES acao(id_acao) ON DELETE CASCADE,
    voluntario_id  INTEGER  NOT NULL,
    movido_por_id  INTEGER,
    status         VARCHAR(20)  NOT NULL,
    compareceu     BOOLEAN      NOT NULL DEFAULT 0,
    observacao     TEXT         NOT NULL DEFAULT '',
    dt_cadastro    DATETIME     NOT NULL,
    dt_movimentacao DATETIME    NOT NULL,
    movido_por_nome VARCHAR(150),
    movido_por_tipo VARCHAR(20),
    restaurado      BOOLEAN     NOT NULL DEFAULT 0,
    restaurado_em   DATETIME,
    restaurado_por_id INTEGER,
    restaurado_por_nome VARCHAR(150),
    restaurado_por_tipo VARCHAR(20)
)""",
    'acao_responsavel': """
CREATE TABLE IF NOT EXISTS acao_responsavel (
    id_acao_responsavel INTEGER PRIMARY KEY AUTOINCREMENT,
    acao_id       INTEGER  NOT NULL REFERENCES acao(id_acao) ON DELETE CASCADE,
    voluntario_id INTEGER  NOT NULL,
    papel         VARCHAR(20) NOT NULL DEFAULT 'RESPONSAVEL',
    UNIQUE (acao_id, voluntario_id)
)""",
}

POSTGRES = {
    'acao': """
CREATE TABLE IF NOT EXISTS acao (
    id_acao       SERIAL PRIMARY KEY,
    tipo          VARCHAR(30)   NOT NULL,
    data          DATE          NOT NULL,
    horario       TIME,
    local         VARCHAR(255)  NOT NULL DEFAULT '',
    descricao     TEXT          NOT NULL DEFAULT '',
    status        VARCHAR(20)   NOT NULL DEFAULT 'PLANEJADA',
    imagens       JSONB         NOT NULL DEFAULT '[]',
    praia_id      INTEGER,
    dt_cadastro   TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    cadastrado_por_id      INTEGER,
    cadastrado_por_nome    VARCHAR(150),
    cadastrado_por_tipo    VARCHAR(20),
    dt_ultima_edicao       TIMESTAMPTZ,
    ultimo_editado_por_id  INTEGER,
    ultimo_editado_por_nome VARCHAR(150),
    ultimo_editado_por_tipo VARCHAR(20)
)""",
    'acao_imagem': """
CREATE TABLE IF NOT EXISTS acao_imagem (
    id_acao_imagem SERIAL PRIMARY KEY,
    acao_id        INTEGER     NOT NULL REFERENCES acao(id_acao) ON DELETE CASCADE,
    imagem         VARCHAR(255) NOT NULL,
    descricao      VARCHAR(255) NOT NULL DEFAULT '',
    dt_cadastro    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
)""",
    'acao_equipe': """
CREATE TABLE IF NOT EXISTS acao_equipe (
    id_acao_equipe SERIAL PRIMARY KEY,
    acao_id        INTEGER NOT NULL REFERENCES acao(id_acao) ON DELETE CASCADE,
    equipe_id      INTEGER NOT NULL,
    UNIQUE (acao_id, equipe_id)
)""",
    'acao_participante': """
CREATE TABLE IF NOT EXISTS acao_participante (
    id_acao_participante SERIAL PRIMARY KEY,
    acao_id        INTEGER     NOT NULL REFERENCES acao(id_acao) ON DELETE CASCADE,
    voluntario_id  INTEGER     NOT NULL,
    status         VARCHAR(20) NOT NULL DEFAULT 'PENDENTE',
    compareceu     BOOLEAN     NOT NULL DEFAULT FALSE,
    observacao     TEXT        NOT NULL DEFAULT '',
    dt_confirmacao TIMESTAMPTZ,
    dt_cadastro    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (acao_id, voluntario_id)
)""",
    'acao_participante_historico': """
CREATE TABLE IF NOT EXISTS acao_participante_historico (
    id_historico    SERIAL PRIMARY KEY,
    acao_id         INTEGER     NOT NULL REFERENCES acao(id_acao) ON DELETE CASCADE,
    voluntario_id   INTEGER     NOT NULL,
    movido_por_id   INTEGER,
    status          VARCHAR(20) NOT NULL,
    compareceu      BOOLEAN     NOT NULL DEFAULT FALSE,
    observacao      TEXT        NOT NULL DEFAULT '',
    dt_cadastro     TIMESTAMPTZ NOT NULL,
    dt_movimentacao TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    movido_por_nome VARCHAR(150),
    movido_por_tipo VARCHAR(20),
    restaurado      BOOLEAN     NOT NULL DEFAULT FALSE,
    restaurado_em   TIMESTAMPTZ,
    restaurado_por_id   INTEGER,
    restaurado_por_nome VARCHAR(150),
    restaurado_por_tipo VARCHAR(20)
)""",
    'acao_responsavel': """
CREATE TABLE IF NOT EXISTS acao_responsavel (
    id_acao_responsavel SERIAL PRIMARY KEY,
    acao_id       INTEGER     NOT NULL REFERENCES acao(id_acao) ON DELETE CASCADE,
    voluntario_id INTEGER     NOT NULL,
    papel         VARCHAR(20) NOT NULL DEFAULT 'RESPONSAVEL',
    UNIQUE (acao_id, voluntario_id)
)""",
}


def _criar(apps, schema_editor):
    sqls = POSTGRES if schema_editor.connection.vendor == 'postgresql' else SQLITE
    for sql in sqls.values():
        schema_editor.execute(sql)


def _reverter(apps, schema_editor):
    for t in reversed(['acao_responsavel', 'acao_participante_historico',
                       'acao_participante', 'acao_equipe', 'acao_imagem', 'acao']):
        schema_editor.execute(f'DROP TABLE IF EXISTS {t}')


class Migration(migrations.Migration):

    dependencies = [
        ('acao', '0001_initial'),
        ('praia', '0003_praia_cadastrado_por_praia_dt_cadastro'),
        ('usuario', '0002_audit_snapshots'),
        ('equipe', '0002_equipe_praia'),
    ]

    operations = [
        migrations.RunPython(_criar, reverse_code=_reverter),
    ]
