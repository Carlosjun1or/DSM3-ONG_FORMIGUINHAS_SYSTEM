"""
Comando Django para sincronizar eventos da base relacional para o MongoDB Atlas.
Uso:
    python manage.py sincronizar_auditoria_mongo
    python manage.py sincronizar_auditoria_mongo --limpar
"""
from django.core.management.base import BaseCommand
from auditoria.models import EventoAuditoria
from auditoria.mongo_services import (
    formatar_documento_auditoria,
    get_auditoria_collection,
)
from config.mongodb import test_mongo_connection


class Command(BaseCommand):
    help = 'Sincroniza todos os eventos de auditoria da base relacional para a coleção no MongoDB Atlas.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limpar',
            action='store_true',
            help='Limpa a coleção no MongoDB Atlas antes de sincronizar os dados.',
        )
        parser.add_argument(
            '--lote',
            type=int,
            default=200,
            help='Tamanho do lote para inserção no MongoDB (padrão: 200).',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('=== Sincronização de Auditoria com MongoDB Atlas ==='))

        # 1. Testa conectividade
        sucesso, msg, info = test_mongo_connection()
        if not sucesso:
            self.stderr.write(self.style.ERROR(f'Falha na conexão com MongoDB Atlas: {msg}'))
            return

        self.stdout.write(self.style.SUCCESS(f'Conectado ao MongoDB Atlas! Banco: {info.get("banco")}'))

        col = get_auditoria_collection()
        if col is None:
            self.stderr.write(self.style.ERROR('Não foi possível obter a coleção de auditoria.'))
            return

        # 2. Opcional: Limpar coleção
        if options['limpar']:
            total_antes = col.count_documents({})
            col.delete_many({})
            self.stdout.write(self.style.WARNING(f'Coleção limpa! ({total_antes} documentos anteriores removidos)'))

        # 3. Lê eventos relacionais
        total_sql = EventoAuditoria.objects.count()
        if total_sql == 0:
            self.stdout.write(self.style.WARNING('Nenhum evento de auditoria encontrado na base relacional.'))
            return

        self.stdout.write(f'Encontrados {total_sql} eventos na base relacional. Iniciando transferência...')

        tamanho_lote = options['lote']
        lote_docs = []
        inseridos = 0

        qs = EventoAuditoria.objects.select_related('usuario__id_voluntario').order_by('id')

        for evento in qs.iterator(chunk_size=tamanho_lote):
            doc = formatar_documento_auditoria(
                entidade=evento.entidade,
                id_registro=evento.id_registro,
                acao=evento.acao,
                usuario=evento.usuario,
                usuario_nome=evento.usuario_nome,
                resumo=evento.resumo,
                valores_anteriores=evento.valores_anteriores,
                valores_novos=evento.valores_novos,
                data_evento=evento.data_evento,
                origem='SINCRONIZACAO_SQL',
            )
            doc['id_sql'] = evento.pk
            lote_docs.append(doc)

            if len(lote_docs) >= tamanho_lote:
                col.insert_many(lote_docs)
                inseridos += len(lote_docs)
                self.stdout.write(f'  -> {inseridos}/{total_sql} documentos sincronizados...')
                lote_docs = []

        if lote_docs:
            col.insert_many(lote_docs)
            inseridos += len(lote_docs)

        total_mongo = col.count_documents({})
        self.stdout.write(self.style.SUCCESS(
            f'\nSincronização concluída com sucesso!'
            f'\nTotal inserido nesta execução: {inseridos}'
            f'\nTotal de documentos no MongoDB Atlas: {total_mongo}'
        ))

