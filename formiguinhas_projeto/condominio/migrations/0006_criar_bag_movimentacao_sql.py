"""
Migration que cria fisicamente as tabelas bag e movimentacao_bag no SQLite.

Contexto: essas tabelas são managed=True (Django as gerencia), mas a tabela
condominio que elas referenciam foi criada pela migration 0005 via RunSQL.
O Django não consegue criar bag/movimentacao_bag via CreateModel porque a
tabela condominio não existia quando as migrations foram primeiro aplicadas.
Esta migration usa IF NOT EXISTS para ser idempotente.
"""
from django.db import migrations


CREATE_BAG = """
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
);
"""

CREATE_MOVIMENTACAO_BAG = """
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
);
"""


class Migration(migrations.Migration):

    dependencies = [
        ('condominio', '0005_criar_tabela_condominio_sql'),
        ('usuario', '0002_audit_snapshots'),
    ]

    operations = [
        migrations.RunSQL(CREATE_BAG,              reverse_sql='DROP TABLE IF EXISTS bag;'),
        migrations.RunSQL(CREATE_MOVIMENTACAO_BAG, reverse_sql='DROP TABLE IF EXISTS movimentacao_bag;'),
    ]
