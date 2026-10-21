"""
Comando Django para sincronizar todos os Comunicados da base relacional para o MongoDB Atlas.
Uso:
    python manage.py sincronizar_comunicados_mongo
    python manage.py sincronizar_comunicados_mongo --limpar
"""
from django.core.management.base import BaseCommand
from comunicado.models import Comunicado
from comunicado.mongo_services import (
    formatar_comunicado_documento,
    get_comunicados_collection,
)
from config.mongodb import test_mongo_connection


class Command(BaseCommand):
    help = 'Sincroniza todos os Comunicados (com Tema, Praias, Equipes, Ações, Doações e Leituras) para o MongoDB Atlas.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limpar',
            action='store_true',
            help='Limpa a coleção no MongoDB Atlas antes de sincronizar os dados.',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('=== Sincronização de Comunicados com MongoDB Atlas (NoSQL) ==='))

        sucesso, msg, info = test_mongo_connection()
        if not sucesso:
            self.stderr.write(self.style.ERROR(f'Falha na conexão com MongoDB Atlas: {msg}'))
            return

        self.stdout.write(self.style.SUCCESS(f'Conectado ao MongoDB Atlas! Banco: {info.get("banco")}'))

        col = get_comunicados_collection()
        if col is None:
            self.stderr.write(self.style.ERROR('Não foi possível obter a coleção comunicados no MongoDB Atlas.'))
            return

        if options['limpar']:
            total_removido = col.count_documents({})
            col.delete_many({})
            self.stdout.write(self.style.WARNING(f'Coleção comunicados limpa ({total_removido} documentos removidos).'))

        qs = Comunicado.objects.select_related(
            'tema',
            'autor__id_voluntario',
            'ultimo_editado_por__id_voluntario',
        ).prefetch_related(
            'praias__praia',
            'equipes__equipe',
            'acoes__acao__praia',
            'doacoes__doacao__doador',
            'leituras__usuario__id_voluntario',
        ).order_by('id_comunicado')

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.WARNING('Nenhum comunicado encontrado na base relacional.'))
            return

        self.stdout.write(f'Encontrados {total} comunicados para migrar. Processando documentos ricos...')

        sincronizados = 0
        for comunicado in qs:
            doc = formatar_comunicado_documento(comunicado)
            col.replace_one({'id_sql': comunicado.pk}, doc, upsert=True)
            sincronizados += 1
            self.stdout.write(
                f'  -> Comunicado #{comunicado.pk} ("{comunicado.titulo[:40]}") sincronizado.'
            )

        total_mongo = col.count_documents({})
        self.stdout.write(self.style.SUCCESS(
            f'\nSincronização de Comunicados concluída com sucesso!'
            f'\nTotal de comunicados processados: {sincronizados}'
            f'\nTotal de documentos na coleção "comunicados" no MongoDB Atlas: {total_mongo}'
        ))

