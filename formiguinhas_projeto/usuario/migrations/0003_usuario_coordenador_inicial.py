from datetime import date

from django.contrib.auth.hashers import make_password
from django.db import migrations

EMAIL = 'coordenador@gmail.com'
SENHA = 'coordenador'


def criar_coordenador(apps, schema_editor):
    Voluntario = apps.get_model('usuario', 'Voluntario')
    Usuario = apps.get_model('usuario', 'Usuario')

    voluntario, _ = Voluntario.objects.get_or_create(
        email=EMAIL,
        defaults={
            'nome': 'Coordenador',
            'dt_nascimento': date(1990, 1, 1),
            'endereco': 'Endereço de teste',
            'telefone': '(13) 99999-9999',
            'status': 'ATIVO',
        },
    )
    Usuario.objects.get_or_create(
        id_voluntario=voluntario,
        defaults={'tipo': 'COORDENADOR', 'senha': make_password(SENHA)},
    )


def remover_coordenador(apps, schema_editor):
    Voluntario = apps.get_model('usuario', 'Voluntario')
    Voluntario.objects.filter(email=EMAIL).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('usuario', '0002_audit_snapshots'),
    ]

    operations = [
        migrations.RunPython(criar_coordenador, remover_coordenador),
    ]
