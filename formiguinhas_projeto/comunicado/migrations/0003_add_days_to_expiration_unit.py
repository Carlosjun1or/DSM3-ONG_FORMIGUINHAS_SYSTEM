from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('comunicado', '0002_duracao_expiracao'),
    ]

    operations = [
        migrations.AlterField(
            model_name='comunicado',
            name='unidade_duracao_expiracao',
            field=models.CharField(
                blank=True,
                choices=[
                    ('DIAS', 'dias'),
                    ('SEMANAS', 'semanas'),
                    ('MESES', 'meses'),
                    ('ANOS', 'anos'),
                ],
                max_length=10,
                null=True,
            ),
        ),
    ]
