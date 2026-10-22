"""
Migration que garante a criação física da tabela condominio no SQLite.

Contexto: a migration 0001 criava esta tabela com managed=True.
A migration 0004 adicionou managed=False. Em um banco zerado criado depois
da migration 0004 ter sido aplicada, o Django não cria a tabela. Esta
migration usa IF NOT EXISTS para ser idempotente (segura em qualquer situação).

Bag e MovimentacaoBag continuam com managed=True e são criadas normalmente.
"""
from django.db import migrations


CREATE_CONDOMINIO = """
CREATE TABLE IF NOT EXISTS condominio (
    id_condominio        INTEGER PRIMARY KEY AUTOINCREMENT,
    nome                 VARCHAR(150) NOT NULL,
    responsavel_nome     VARCHAR(150) NOT NULL,
    responsavel_telefone VARCHAR(20)  NOT NULL,
    responsavel_email    VARCHAR(254) NOT NULL DEFAULT '',
    endereco             VARCHAR(255) NOT NULL,
    numero               VARCHAR(20)  NOT NULL,
    complemento          VARCHAR(100) NOT NULL DEFAULT '',
    bairro               VARCHAR(100) NOT NULL,
    cidade               VARCHAR(100) NOT NULL,
    estado               VARCHAR(2)   NOT NULL DEFAULT 'SP',
    cep                  VARCHAR(9)   NOT NULL DEFAULT '',
    porte                VARCHAR(20)  NOT NULL DEFAULT 'MEDIO',
    confiabilidade       VARCHAR(20)  NOT NULL DEFAULT 'EM_AVALIACAO',
    status               VARCHAR(20)  NOT NULL DEFAULT 'ATIVO',
    observacoes          TEXT         NOT NULL DEFAULT '',
    dt_cadastro          DATETIME     NOT NULL,
    cadastrado_por_id    INTEGER      REFERENCES usuario(id_usuario) ON DELETE SET NULL,
    cadastrado_por_nome  VARCHAR(150) NOT NULL DEFAULT '',
    dt_ultima_edicao     DATETIME,
    ultimo_editado_por_id INTEGER     REFERENCES usuario(id_usuario) ON DELETE SET NULL,
    ultimo_editado_por_nome VARCHAR(150) NOT NULL DEFAULT '',
    praia_id             INTEGER      REFERENCES praia(id_praia) ON DELETE SET NULL
);
"""


class Migration(migrations.Migration):

    dependencies = [
        ('condominio', '0004_alter_condominio_options'),
        ('usuario', '0002_audit_snapshots'),
        ('praia', '0003_praia_cadastrado_por_praia_dt_cadastro'),
    ]

    operations = [
        migrations.RunSQL(
            CREATE_CONDOMINIO,
            reverse_sql='DROP TABLE IF EXISTS condominio;',
        ),
    ]
