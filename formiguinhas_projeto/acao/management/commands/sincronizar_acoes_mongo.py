"""
Comando Django para sincronizar todas as Ações de Limpeza de Praia para a coleção no MongoDB Atlas.
Uso:
    python manage.py sincronizar_acoes_mongo
    python manage.py sincronizar_acoes_mongo --limpar
"""
from django.core.management.base import BaseCommand
from acao.models import Acao
from acao.mongo_services import (
    formatar_acao_documento,
    get_acoes_collection,
)
from config.mongodb import test_mongo_connection


class Command(BaseCommand):
    help = 'Sincroniza todas as Ações (com participantes, equipes, imagens, praia e resíduos) para o MongoDB Atlas.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limpar',
            action='store_true',
            help='Limpa a coleção no MongoDB Atlas antes de sincronizar os dados.',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('=== Sincronização de Ações com MongoDB Atlas (NoSQL) ==='))

        sucesso, msg, info = test_mongo_connection()
        if not sucesso:
            self.stderr.write(self.style.ERROR(f'Falha na conexão com MongoDB Atlas: {msg}'))
            return

        self.stdout.write(self.style.SUCCESS(f'Conectado ao MongoDB Atlas! Banco: {info.get("banco")}'))

        col = get_acoes_collection()
        if col is None:
            self.stderr.write(self.style.ERROR('Não foi possível obter a coleção acoes no MongoDB Atlas.'))
            return

        if options['limpar']:
            total_removido = col.count_documents({})
            col.delete_many({})
            self.stdout.write(self.style.WARNING(f'Coleção acoes limpa ({total_removido} documentos removidos).'))

        qs = Acao.objects.select_related(
            'praia',
            'cadastrado_por__id_voluntario',
            'ultimo_editado_por__id_voluntario',
        ).prefetch_related(
            'equipes_vinculadas__equipe__praia',
            'responsaveis__voluntario',
            'participantes__voluntario',
            'historico_participantes__voluntario',
            'imagens_acao',
            'residuos_coletados__destinacoes',
        ).order_by('id_acao')

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.WARNING('Nenhuma ação encontrada na base relacional.'))
            return

        self.stdout.write(f'Encontradas {total} ações para migrar. Processando documentos ricos com subdocumentos...')

        sincronizadas = 0
        for acao in qs:
            doc = formatar_acao_documento(acao)
            col.replace_one({'id_sql': acao.pk}, doc, upsert=True)
            sincronizadas += 1
            self.stdout.write(f'  -> Ação #{acao.pk} ("{acao.get_tipo_display()} - {acao.praia.nome}") sincronizada.')

        total_mongo = col.count_documents({})
        self.stdout.write(self.style.SUCCESS(
            f'\nSincronização de Ações concluída com sucesso!'
            f'\nTotal de ações processadas: {sincronizadas}'
            f'\nTotal de documentos na coleção "acoes" no MongoDB Atlas: {total_mongo}'
        ))

