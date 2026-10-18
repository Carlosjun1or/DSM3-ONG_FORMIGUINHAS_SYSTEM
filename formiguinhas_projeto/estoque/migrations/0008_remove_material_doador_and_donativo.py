from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('estoque', '0006_alter_material_unidade'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='material',
            name='doador',
        ),
        migrations.RemoveField(
            model_name='material',
            name='donativo',
        ),
    ]
