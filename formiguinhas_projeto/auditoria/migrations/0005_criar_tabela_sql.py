"""
Migration que garante a criação física da tabela auditoria_eventoauditoria no SQLite.

Contexto: a migration 0001 criava esta tabela com managed=True. A migration 0004
adicionou managed=False, mas isso não apaga a tabela existente. Porém, em um banco
zerado (clone novo do repositório), rodar migrate executa a 0004 que apenas muda
metadados do Django — a tabela pode não ter sido criada se o Django pulou a criação
por detectar managed=False. Esta migration usa IF NOT EXISTS para ser idempotente.
"""
from django.db import migrations


CREATE_EVENTO_AUDITORIA = """
CREATE TABLE IF NOT EXISTS auditoria_eventoauditoria (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    entidade        VARCHAR(40)  NOT NULL,
    id_registro     INTEGER,
    acao            VARCHAR(20)  NOT NULL,
    usuario_id      INTEGER      REFERENCES usuario(id_usuario) ON DELETE SET NULL,
    usuario_nome    VARCHAR(150) NOT NULL DEFAULT '',
    data_evento     DATETIME     NOT NULL,
    resumo          VARCHAR(255) NOT NULL,
    valores_anteriores JSON      NOT NULL DEFAULT '{}',
    valores_novos      JSON      NOT NULL DEFAULT '{}'
);
"""

CREATE_IDX1 = """
CREATE INDEX IF NOT EXISTS auditoria_e_entidad_ff160b_idx
    ON auditoria_eventoauditoria (entidade, acao);
"""

CREATE_IDX2 = """
CREATE INDEX IF NOT EXISTS auditoria_e_data_ev_0b4a96_idx
    ON auditoria_eventoauditoria (data_evento);
"""

CREATE_IDX3 = """
CREATE INDEX IF NOT EXISTS auditoria_e_usuario_3d442a_idx
    ON auditoria_eventoauditoria (usuario_id);
"""


class Migration(migrations.Migration):

    dependencies = [
        ('auditoria', '0004_alter_eventoauditoria_options'),
        ('usuario', '0002_audit_snapshots'),
    ]

    operations = [
        migrations.RunSQL(CREATE_EVENTO_AUDITORIA, reverse_sql='DROP TABLE IF EXISTS auditoria_eventoauditoria;'),
        migrations.RunSQL(CREATE_IDX1, reverse_sql='DROP INDEX IF EXISTS auditoria_e_entidad_ff160b_idx;'),
        migrations.RunSQL(CREATE_IDX2, reverse_sql='DROP INDEX IF EXISTS auditoria_e_data_ev_0b4a96_idx;'),
        migrations.RunSQL(CREATE_IDX3, reverse_sql='DROP INDEX IF EXISTS auditoria_e_usuario_3d442a_idx;'),
    ]
