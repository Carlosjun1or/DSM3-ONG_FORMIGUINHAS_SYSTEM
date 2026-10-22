"""
Migration que cria fisicamente as tabelas do app 'comunicado' no SQLite.

Contexto: a migration 0006 marcou todos os models como managed=False,
portanto o Django parou de gerenciá-los. As tabelas que já existiam
continuaram funcionando, mas em um banco zerado elas nunca são criadas.
Esta migration usa RunSQL para criá-las com IF NOT EXISTS — seguro tanto
em bancos novos quanto em bancos que já tinham as tabelas.
"""
from django.db import migrations


CREATE_TEMA = """
CREATE TABLE IF NOT EXISTS comunicado_tema (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    nome          VARCHAR(120) NOT NULL UNIQUE,
    descricao     TEXT         NOT NULL DEFAULT '',
    ativo         BOOLEAN      NOT NULL DEFAULT 1,
    criado_por_id    INTEGER,
    atualizado_por_id INTEGER,
    criado_em     DATETIME     NOT NULL,
    atualizado_em DATETIME     NOT NULL
);
"""

CREATE_COMUNICADO = """
CREATE TABLE IF NOT EXISTS comunicado (
    id_comunicado INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo          VARCHAR(10)  NOT NULL,
    titulo        VARCHAR(200) NOT NULL,
    resumo        VARCHAR(500) NOT NULL DEFAULT '',
    conteudo      TEXT         NOT NULL,
    publico       VARCHAR(15)  NOT NULL DEFAULT 'TODOS',
    status        VARCHAR(12)  NOT NULL DEFAULT 'RASCUNHO',
    tema_id       INTEGER      REFERENCES comunicado_tema(id) ON DELETE RESTRICT,
    dt_publicacao DATETIME,
    dt_expiracao  DATETIME,
    duracao_expiracao    INTEGER,
    unidade_duracao_expiracao VARCHAR(10),
    autor_id      INTEGER,
    perfil_autor  VARCHAR(20)  NOT NULL DEFAULT '',
    ultimo_editado_por_id INTEGER,
    dt_ultima_edicao DATETIME,
    criado_em     DATETIME     NOT NULL,
    atualizado_em DATETIME     NOT NULL
);
"""

CREATE_COMUNICADO_IDX1 = """
CREATE INDEX IF NOT EXISTS comunicado_status_553339_idx
    ON comunicado (status, publico, dt_publicacao);
"""

CREATE_COMUNICADO_IDX2 = """
CREATE INDEX IF NOT EXISTS comunicado_tipo_2cfb9c_idx
    ON comunicado (tipo, status);
"""

CREATE_COMUNICADO_PRAIA = """
CREATE TABLE IF NOT EXISTS comunicado_praia (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    comunicado_id INTEGER NOT NULL REFERENCES comunicado(id_comunicado) ON DELETE CASCADE,
    praia_id      INTEGER NOT NULL,
    UNIQUE (comunicado_id, praia_id)
);
"""

CREATE_COMUNICADO_EQUIPE = """
CREATE TABLE IF NOT EXISTS comunicado_equipe (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    comunicado_id INTEGER NOT NULL REFERENCES comunicado(id_comunicado) ON DELETE CASCADE,
    equipe_id     INTEGER NOT NULL,
    UNIQUE (comunicado_id, equipe_id)
);
"""

CREATE_COMUNICADO_ACAO = """
CREATE TABLE IF NOT EXISTS comunicado_acao (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    comunicado_id INTEGER NOT NULL REFERENCES comunicado(id_comunicado) ON DELETE CASCADE,
    acao_id       INTEGER NOT NULL,
    UNIQUE (comunicado_id, acao_id)
);
"""

CREATE_COMUNICADO_DOACAO = """
CREATE TABLE IF NOT EXISTS comunicado_doacao (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    comunicado_id INTEGER NOT NULL REFERENCES comunicado(id_comunicado) ON DELETE CASCADE,
    doacao_id     INTEGER NOT NULL,
    UNIQUE (comunicado_id, doacao_id)
);
"""

CREATE_COMUNICADO_LEITURA = """
CREATE TABLE IF NOT EXISTS comunicado_leitura (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    comunicado_id INTEGER NOT NULL REFERENCES comunicado(id_comunicado) ON DELETE CASCADE,
    usuario_id    INTEGER NOT NULL,
    lido_em       DATETIME NOT NULL,
    UNIQUE (comunicado_id, usuario_id)
);
"""

CREATE_LEITURA_IDX = """
CREATE INDEX IF NOT EXISTS comunicado__usuario_bee43b_idx
    ON comunicado_leitura (usuario_id, lido_em);
"""


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
        migrations.RunSQL(CREATE_TEMA,              reverse_sql='DROP TABLE IF EXISTS comunicado_tema;'),
        migrations.RunSQL(CREATE_COMUNICADO,         reverse_sql='DROP TABLE IF EXISTS comunicado;'),
        migrations.RunSQL(CREATE_COMUNICADO_IDX1,    reverse_sql='DROP INDEX IF EXISTS comunicado_status_553339_idx;'),
        migrations.RunSQL(CREATE_COMUNICADO_IDX2,    reverse_sql='DROP INDEX IF EXISTS comunicado_tipo_2cfb9c_idx;'),
        migrations.RunSQL(CREATE_COMUNICADO_PRAIA,   reverse_sql='DROP TABLE IF EXISTS comunicado_praia;'),
        migrations.RunSQL(CREATE_COMUNICADO_EQUIPE,  reverse_sql='DROP TABLE IF EXISTS comunicado_equipe;'),
        migrations.RunSQL(CREATE_COMUNICADO_ACAO,    reverse_sql='DROP TABLE IF EXISTS comunicado_acao;'),
        migrations.RunSQL(CREATE_COMUNICADO_DOACAO,  reverse_sql='DROP TABLE IF EXISTS comunicado_doacao;'),
        migrations.RunSQL(CREATE_COMUNICADO_LEITURA, reverse_sql='DROP TABLE IF EXISTS comunicado_leitura;'),
        migrations.RunSQL(CREATE_LEITURA_IDX,        reverse_sql='DROP INDEX IF EXISTS comunicado__usuario_bee43b_idx;'),
    ]
