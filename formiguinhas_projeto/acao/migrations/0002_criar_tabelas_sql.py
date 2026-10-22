"""
Migration que cria fisicamente as tabelas do app 'acao' no SQLite.

Contexto: todos os models deste app têm managed=False desde a migration inicial,
portanto o Django nunca as criou via migrate. Como o código ORM ainda precisa
dessas tabelas (save, filter, get_object_or_404, etc.), elas são criadas aqui
via RunSQL. O MongoDB Atlas continua sendo a fonte primária para leituras —
o SQLite serve como backend de escrita/leitura relacional de apoio.
"""
from django.db import migrations


CREATE_ACAO = """
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
);
"""

CREATE_ACAO_IMAGEM = """
CREATE TABLE IF NOT EXISTS acao_imagem (
    id_acao_imagem INTEGER PRIMARY KEY AUTOINCREMENT,
    acao_id        INTEGER  NOT NULL REFERENCES acao(id_acao) ON DELETE CASCADE,
    imagem         VARCHAR(100) NOT NULL,
    descricao      VARCHAR(255) NOT NULL DEFAULT '',
    dt_cadastro    DATETIME     NOT NULL
);
"""

CREATE_ACAO_EQUIPE = """
CREATE TABLE IF NOT EXISTS acao_equipe (
    id_acao_equipe INTEGER PRIMARY KEY AUTOINCREMENT,
    acao_id        INTEGER NOT NULL REFERENCES acao(id_acao) ON DELETE CASCADE,
    equipe_id      INTEGER NOT NULL,
    UNIQUE (acao_id, equipe_id)
);
"""

CREATE_ACAO_PARTICIPANTE = """
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
);
"""

CREATE_ACAO_PARTICIPANTE_HISTORICO = """
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
);
"""

CREATE_ACAO_RESPONSAVEL = """
CREATE TABLE IF NOT EXISTS acao_responsavel (
    id_acao_responsavel INTEGER PRIMARY KEY AUTOINCREMENT,
    acao_id       INTEGER  NOT NULL REFERENCES acao(id_acao) ON DELETE CASCADE,
    voluntario_id INTEGER  NOT NULL,
    papel         VARCHAR(20) NOT NULL DEFAULT 'RESPONSAVEL',
    UNIQUE (acao_id, voluntario_id)
);
"""


class Migration(migrations.Migration):

    dependencies = [
        ('acao', '0001_initial'),
        ('praia', '0003_praia_cadastrado_por_praia_dt_cadastro'),
        ('usuario', '0002_audit_snapshots'),
        ('equipe', '0002_equipe_praia'),
    ]

    operations = [
        migrations.RunSQL(CREATE_ACAO,                      reverse_sql='DROP TABLE IF EXISTS acao;'),
        migrations.RunSQL(CREATE_ACAO_IMAGEM,               reverse_sql='DROP TABLE IF EXISTS acao_imagem;'),
        migrations.RunSQL(CREATE_ACAO_EQUIPE,               reverse_sql='DROP TABLE IF EXISTS acao_equipe;'),
        migrations.RunSQL(CREATE_ACAO_PARTICIPANTE,         reverse_sql='DROP TABLE IF EXISTS acao_participante;'),
        migrations.RunSQL(CREATE_ACAO_PARTICIPANTE_HISTORICO, reverse_sql='DROP TABLE IF EXISTS acao_participante_historico;'),
        migrations.RunSQL(CREATE_ACAO_RESPONSAVEL,          reverse_sql='DROP TABLE IF EXISTS acao_responsavel;'),
    ]
