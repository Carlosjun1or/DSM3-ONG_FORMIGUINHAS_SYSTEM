"""
Comando Django para sincronizar todos os Condominios da base relacional para o MongoDB Atlas.
Uso:
    python manage.py sincronizar_condominios_mongo
    python manage.py sincronizar_condominios_mongo --limpar
"""
from django.core.management.base import BaseCommand
from condominio.models import Condominio
from condominio.mongo_services import (
    formatar_condominio_documento,
    get_condominios_collection,
)
from config.mongodb import test_mongo_connection


class Command(BaseCommand):
    help = 'Sincroniza todos os Condominios (com Bags e Movimentacoes) para o MongoDB Atlas.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limpar',
            action='store_true',
            help='Limpa a colecao no MongoDB Atlas antes de sincronizar os dados.',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('=== Sincronizacao de Condominios com MongoDB Atlas (NoSQL) ==='))

        sucesso, msg, info = test_mongo_connection()
        if not sucesso:
            self.stderr.write(self.style.ERROR(f'Falha na conexao com MongoDB Atlas: {msg}'))
            return

        self.stdout.write(self.style.SUCCESS(f'Conectado ao MongoDB Atlas! Banco: {info.get("banco")}'))

        col = get_condominios_collection()
        if col is None:
            self.stderr.write(self.style.ERROR('Nao foi possivel obter a colecao condominios no MongoDB Atlas.'))
            return

        if options['limpar']:
            total_removido = col.count_documents({})
            col.delete_many({})
            self.stdout.write(self.style.WARNING(f'Colecao condominios limpa ({total_removido} documentos removidos).'))

        qs = Condominio.objects.select_related(
            'praia',
            'cadastrado_por__id_voluntario',
            'ultimo_editado_por__id_voluntario',
        ).prefetch_related(
            'bags__movimentacoes__registrado_por__id_voluntario',
            'bags__cadastrado_por__id_voluntario',
            'bags__ultimo_editado_por__id_voluntario',
        ).order_by('id_condominio')

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.WARNING('Nenhum condominio encontrado na base relacional.'))
            return

        self.stdout.write(f'Encontrados {total} condominios para migrar. Processando documentos ricos...')

        sincronizados = 0
        for condominio in qs:
            doc = formatar_condominio_documento(condominio)
            col.replace_one({'id_sql': condominio.pk}, doc, upsert=True)
            sincronizados += 1
            total_bags = len(doc.get('bags', []))
            self.stdout.write(
                f'  -> Condominio #{condominio.pk} ("{condominio.nome}") '
                f'sincronizado com {total_bags} bag(s).'
            )

        total_mongo = col.count_documents({})
        self.stdout.write(self.style.SUCCESS(
            f'\nSincronizacao de Condominios concluida com sucesso!'
            f'\nTotal de condominios processados: {sincronizados}'
            f'\nTotal de documentos na colecao "condominios" no MongoDB Atlas: {total_mongo}'
        ))

