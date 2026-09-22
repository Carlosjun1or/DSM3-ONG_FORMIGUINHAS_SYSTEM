from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [('usuario', '0002_audit_snapshots')]
    operations = [migrations.CreateModel(
        name='EventoAuditoria',
        fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('entidade', models.CharField(max_length=40)),
            ('id_registro', models.PositiveIntegerField(blank=True, null=True)),
            ('acao', models.CharField(choices=[('CRIACAO', 'Criação'), ('EDICAO', 'Edição'), ('MUDANCA_STATUS', 'Mudança de status'), ('VINCULO', 'Vínculo'), ('EXCLUSAO', 'Exclusão'), ('MOVIMENTACAO', 'Movimentação')], max_length=20)),
            ('usuario_nome', models.CharField(blank=True, max_length=150)),
            ('data_evento', models.DateTimeField(auto_now_add=True)),
            ('resumo', models.CharField(max_length=255)),
            ('valores_anteriores', models.JSONField(blank=True, default=dict)),
            ('valores_novos', models.JSONField(blank=True, default=dict)),
            ('usuario', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='eventos_auditoria', to='usuario.usuario')),
        ],
        options={'ordering': ('-data_evento', '-id')},
    ), migrations.AddIndex(model_name='eventoauditoria', index=models.Index(fields=['entidade', 'acao'], name='auditoria_e_entidad_8d2c2b_idx')), migrations.AddIndex(model_name='eventoauditoria', index=models.Index(fields=['data_evento'], name='auditoria_e_data_ev_0b4a96_idx')), migrations.AddIndex(model_name='eventoauditoria', index=models.Index(fields=['usuario'], name='auditoria_e_usuario_3d442a_idx'))]
