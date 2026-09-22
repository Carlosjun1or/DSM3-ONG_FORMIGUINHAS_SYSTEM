from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('condominio', '0002_auditoriacontrole'),
    ]

    operations = [
        migrations.DeleteModel(
            name='AuditoriaControle',
        ),
    ]
