import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('comunicado', '0004_comunicadoleitura'),
        ('doacao', '0002_doador_doador_documento_unico_nao_vazio_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='ComunicadoDoacao',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                (
                    'comunicado',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='doacoes',
                        to='comunicado.comunicado',
                    ),
                ),
                (
                    'doacao',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='comunicados',
                        to='doacao.doacao',
                    ),
                ),
            ],
            options={
                'db_table': 'comunicado_doacao',
                'constraints': [
                    models.UniqueConstraint(
                        fields=('comunicado', 'doacao'),
                        name='comunicado_doacao_unico',
                    ),
                ],
            },
        ),
    ]
