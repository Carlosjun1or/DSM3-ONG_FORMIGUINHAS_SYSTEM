from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usuario', '0001_initial_consolidada'),
    ]

    operations = [
        migrations.AddField(
            model_name='voluntario',
            name='cadastrado_por_nome',
            field=models.CharField(blank=True, max_length=150, null=True),
        ),
        migrations.AddField(
            model_name='voluntario',
            name='cadastrado_por_tipo',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name='voluntario',
            name='ultimo_editado_por_nome',
            field=models.CharField(blank=True, max_length=150, null=True),
        ),
        migrations.AddField(
            model_name='voluntario',
            name='ultimo_editado_por_tipo',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name='usuario',
            name='cadastrado_por_nome',
            field=models.CharField(blank=True, max_length=150, null=True),
        ),
        migrations.AddField(
            model_name='usuario',
            name='cadastrado_por_tipo',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name='usuario',
            name='ultimo_editado_por_nome',
            field=models.CharField(blank=True, max_length=150, null=True),
        ),
        migrations.AddField(
            model_name='usuario',
            name='ultimo_editado_por_tipo',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
    ]
