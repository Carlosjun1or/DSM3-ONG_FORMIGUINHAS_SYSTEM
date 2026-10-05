from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('comunicado', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='comunicado',
            name='duracao_expiracao',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='comunicado',
            name='unidade_duracao_expiracao',
            field=models.CharField(
                blank=True,
                choices=[
                    ('SEMANAS', 'semanas'),
                    ('MESES', 'meses'),
                    ('ANOS', 'anos'),
                ],
                max_length=10,
                null=True,
            ),
        ),
    ]
