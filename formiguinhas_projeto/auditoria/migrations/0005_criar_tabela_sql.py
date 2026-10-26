"""
Migration que garante a criação física da tabela auditoria_eventoauditoria.
Compatível com SQLite e PostgreSQL.
"""
from django.db import migrations

SQLITE_TABLE = """
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
)
"""

POSTGRES_TABLE = """
CREATE TABLE IF NOT EXISTS auditoria_eventoauditoria (
    id              SERIAL PRIMARY KEY,
    entidade        VARCHAR(40)  NOT NULL,
    id_registro     INTEGER,
    acao            VARCHAR(20)  NOT NULL,
    usuario_id      INTEGER      REFERENCES usuario(id_usuario) ON DELETE SET NULL,
    usuario_nome    VARCHAR(150) NOT NULL DEFAULT '',
    data_evento     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    resumo          VARCHAR(255) NOT NULL,
    valores_anteriores JSONB     NOT NULL DEFAULT '{}',
    valores_novos      JSONB     NOT NULL DEFAULT '{}'
)
"""

IDX1 = "CREATE INDEX IF NOT EXISTS auditoria_e_entidad_ff160b_idx ON auditoria_eventoauditoria (entidade, acao)"
IDX2 = "CREATE INDEX IF NOT EXISTS auditoria_e_data_ev_0b4a96_idx ON auditoria_eventoauditoria (data_evento)"
IDX3 = "CREATE INDEX IF NOT EXISTS auditoria_e_usuario_3d442a_idx ON auditoria_eventoauditoria (usuario_id)"


def _criar(apps, schema_editor):
    sql = POSTGRES_TABLE if schema_editor.connection.vendor == 'postgresql' else SQLITE_TABLE
    schema_editor.execute(sql)
    schema_editor.execute(IDX1)
    schema_editor.execute(IDX2)
    schema_editor.execute(IDX3)


def _reverter(apps, schema_editor):
    schema_editor.execute('DROP INDEX IF EXISTS auditoria_e_entidad_ff160b_idx')
    schema_editor.execute('DROP INDEX IF EXISTS auditoria_e_data_ev_0b4a96_idx')
    schema_editor.execute('DROP INDEX IF EXISTS auditoria_e_usuario_3d442a_idx')
    schema_editor.execute('DROP TABLE IF EXISTS auditoria_eventoauditoria')


class Migration(migrations.Migration):

    dependencies = [
        ('auditoria', '0004_alter_eventoauditoria_options'),
        ('usuario', '0002_audit_snapshots'),
    ]

    operations = [
        migrations.RunPython(_criar, reverse_code=_reverter),
    ]
