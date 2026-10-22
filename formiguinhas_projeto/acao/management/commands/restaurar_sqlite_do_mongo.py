"""
Comando Django para restaurar os dados do MongoDB Atlas de volta para o SQLite.

Uso:
    python manage.py restaurar_sqlite_do_mongo
    python manage.py restaurar_sqlite_do_mongo --apenas acoes
    python manage.py restaurar_sqlite_do_mongo --apenas comunicados
    python manage.py restaurar_sqlite_do_mongo --apenas condominios

Contexto:
    O banco SQLite foi recriado do zero (via migrate) e ficou vazio,
    mas o MongoDB Atlas possui os dados originais. Este comando inverte
    o fluxo de sincronização: lê os documentos do Mongo e reconstrói
    os registros relacionais no SQLite, preservando os IDs originais (id_sql).
"""
from datetime import date, datetime, time as dt_time

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.dateparse import parse_date, parse_datetime, parse_time

from config.mongodb import test_mongo_connection, get_mongo_db


def _dt(val):
    """Converte string ISO ou objeto datetime/date para o tipo correto."""
    if val is None:
        return None
    if isinstance(val, (datetime, date)):
        return val
    if isinstance(val, str):
        parsed = parse_datetime(val)
        if parsed:
            return parsed
        parsed = parse_date(val)
        if parsed:
            return parsed
    return None


def _time(val):
    if val is None:
        return None
    if isinstance(val, dt_time):
        return val
    if isinstance(val, str):
        return parse_time(val)
    return None


class Command(BaseCommand):
    help = 'Restaura dados do MongoDB Atlas para o SQLite (sentido inverso da sincronização).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apenas',
            choices=['acoes', 'comunicados', 'condominios', 'auditoria'],
            default=None,
            help='Restaura apenas uma coleção específica (padrão: todas).',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING(
            '=== Restauração do SQLite a partir do MongoDB Atlas ==='
        ))

        sucesso, msg, info = test_mongo_connection(forcar=True)
        if not sucesso:
            self.stderr.write(self.style.ERROR(f'Sem conexão com MongoDB Atlas: {msg}'))
            return
        self.stdout.write(self.style.SUCCESS(f'Conectado! Banco: {info.get("banco")}'))

        apenas = options.get('apenas')
        if apenas is None or apenas == 'acoes':
            self._restaurar_acoes()
        if apenas is None or apenas == 'comunicados':
            self._restaurar_comunicados()
        if apenas is None or apenas == 'condominios':
            self._restaurar_condominios()
        if apenas is None or apenas == 'auditoria':
            self._restaurar_auditoria()

        self.stdout.write(self.style.SUCCESS('\nRestauração concluída.'))

    # ──────────────────────────────────────────────────────────────────────────
    # AÇÕES
    # ──────────────────────────────────────────────────────────────────────────

    def _restaurar_acoes(self):
        from acao.models import (
            Acao, AcaoEquipe, AcaoImagem,
            AcaoParticipante, AcaoParticipanteHistorico, AcaoResponsavel,
        )
        from praia.models import Praia
        from usuario.models import Voluntario

        db = get_mongo_db()
        colecao = db['acoes']
        docs = list(colecao.find({}))

        self.stdout.write(f'\n[Ações] {len(docs)} documentos encontrados no MongoDB.')
        if not docs:
            return

        restauradas = 0
        erros = 0

        for doc in docs:
            id_sql = doc.get('id_sql')
            if not id_sql:
                self.stdout.write(self.style.WARNING(f'  Documento sem id_sql ignorado: {doc.get("_id")}'))
                continue

            try:
                with transaction.atomic():
                    # Praia
                    praia_doc = doc.get('praia') or {}
                    praia = Praia.objects.filter(pk=praia_doc.get('id') or praia_doc.get('id_praia')).first()

                    # Ação principal
                    acao, criada = Acao.objects.update_or_create(
                        id_acao=id_sql,
                        defaults={
                            'tipo': doc.get('tipo', 'MUTIRAO'),
                            'data': _dt(doc.get('data')) or date.today(),
                            'horario': _time(doc.get('horario')),
                            'local': doc.get('local', ''),
                            'descricao': doc.get('descricao', ''),
                            'status': doc.get('status', 'PLANEJADA'),
                            'imagens': doc.get('imagens', []),
                            'praia': praia,
                            'dt_cadastro': _dt(doc.get('dt_cadastro')) or datetime.now(),
                            'cadastrado_por_nome': doc.get('cadastrado_por_nome', ''),
                            'cadastrado_por_tipo': (doc.get('cadastrado_por') or {}).get('tipo', ''),
                            'dt_ultima_edicao': _dt(doc.get('dt_ultima_edicao')),
                            'ultimo_editado_por_nome': doc.get('ultimo_editado_por_nome', ''),
                        },
                    )
                    prefixo = 'Criada' if criada else 'Atualizada'

                    # Equipes
                    AcaoEquipe.objects.filter(acao=acao).delete()
                    for eq_doc in doc.get('equipes', []):
                        equipe_id = eq_doc.get('id')
                        if equipe_id:
                            AcaoEquipe.objects.get_or_create(
                                acao=acao,
                                equipe_id=equipe_id,
                            )

                    # Responsáveis
                    AcaoResponsavel.objects.filter(acao=acao).delete()
                    for resp_doc in doc.get('responsaveis', []):
                        vol_id = resp_doc.get('voluntario_id')
                        if vol_id and Voluntario.objects.filter(pk=vol_id).exists():
                            AcaoResponsavel.objects.get_or_create(
                                acao=acao,
                                voluntario_id=vol_id,
                                defaults={'papel': resp_doc.get('papel', 'RESPONSAVEL')},
                            )

                    # Participantes
                    AcaoParticipante.objects.filter(acao=acao).delete()
                    for part_doc in doc.get('participantes', []):
                        vol_id = part_doc.get('voluntario_id')
                        if vol_id and Voluntario.objects.filter(pk=vol_id).exists():
                            AcaoParticipante.objects.get_or_create(
                                acao=acao,
                                voluntario_id=vol_id,
                                defaults={
                                    'status': part_doc.get('status', 'PENDENTE'),
                                    'compareceu': bool(part_doc.get('compareceu', False)),
                                    'observacao': part_doc.get('observacao', ''),
                                    'dt_confirmacao': _dt(part_doc.get('dt_confirmacao')),
                                    'dt_cadastro': _dt(part_doc.get('dt_cadastro')) or datetime.now(),
                                },
                            )

                    # Histórico de participantes removidos
                    AcaoParticipanteHistorico.objects.filter(acao=acao).delete()
                    for hist_doc in doc.get('historico_participantes', []):
                        vol_id = hist_doc.get('voluntario_id')
                        if vol_id and Voluntario.objects.filter(pk=vol_id).exists():
                            AcaoParticipanteHistorico.objects.create(
                                acao=acao,
                                voluntario_id=vol_id,
                                status=hist_doc.get('status', 'PENDENTE'),
                                compareceu=bool(hist_doc.get('compareceu', False)),
                                observacao=hist_doc.get('observacao', ''),
                                dt_cadastro=_dt(hist_doc.get('dt_cadastro')) or datetime.now(),
                                movido_por_nome=hist_doc.get('movido_por_nome', ''),
                                movido_por_tipo=hist_doc.get('movido_por_tipo', ''),
                                restaurado=bool(hist_doc.get('restaurado', False)),
                                restaurado_em=_dt(hist_doc.get('restaurado_em')),
                                restaurado_por_nome=hist_doc.get('restaurado_por_nome', ''),
                                restaurado_por_tipo=hist_doc.get('restaurado_por_tipo', ''),
                            )

                    restauradas += 1
                    self.stdout.write(f'  [{prefixo}] Ação #{id_sql}: {doc.get("tipo", "")} - {praia_doc.get("nome", "")}')

            except Exception as e:
                erros += 1
                self.stdout.write(self.style.ERROR(f'  [ERRO] Ação #{id_sql}: {e}'))

        self.stdout.write(self.style.SUCCESS(
            f'[Ações] {restauradas} restauradas, {erros} erros.'
        ))

    # ──────────────────────────────────────────────────────────────────────────
    # COMUNICADOS
    # ──────────────────────────────────────────────────────────────────────────

    def _restaurar_comunicados(self):
        from comunicado.models import (
            Tema, Comunicado,
            ComunicadoPraia, ComunicadoEquipe,
            ComunicadoAcao, ComunicadoDoacao,
        )

        db = get_mongo_db()
        colecao = db['comunicados']
        docs = list(colecao.find({}))

        self.stdout.write(f'\n[Comunicados] {len(docs)} documentos encontrados no MongoDB.')
        if not docs:
            return

        restaurados = 0
        erros = 0

        for doc in docs:
            id_sql = doc.get('id_sql')
            if not id_sql:
                continue

            try:
                with transaction.atomic():
                    # Tema
                    tema = None
                    tema_doc = doc.get('tema')
                    if tema_doc:
                        tema, _ = Tema.objects.update_or_create(
                            id=tema_doc.get('id'),
                            defaults={
                                'nome': tema_doc.get('nome', ''),
                                'descricao': tema_doc.get('descricao', ''),
                                'ativo': bool(tema_doc.get('ativo', True)),
                            },
                        )

                    # Comunicado principal
                    comunicado, criado = Comunicado.objects.update_or_create(
                        id_comunicado=id_sql,
                        defaults={
                            'tipo': doc.get('tipo', 'AVISO'),
                            'titulo': doc.get('titulo', ''),
                            'resumo': doc.get('resumo', ''),
                            'conteudo': doc.get('conteudo', ''),
                            'publico': doc.get('publico', 'TODOS'),
                            'status': doc.get('status', 'RASCUNHO'),
                            'tema': tema,
                            'dt_publicacao': _dt(doc.get('dt_publicacao')),
                            'dt_expiracao': _dt(doc.get('dt_expiracao')),
                            'perfil_autor': doc.get('perfil_autor', ''),
                            'dt_ultima_edicao': _dt(doc.get('dt_ultima_edicao')),
                            'criado_em': _dt(doc.get('criado_em')) or datetime.now(),
                            'atualizado_em': _dt(doc.get('atualizado_em')) or datetime.now(),
                        },
                    )
                    prefixo = 'Criado' if criado else 'Atualizado'

                    # Relacionamentos — praias
                    ComunicadoPraia.objects.filter(comunicado=comunicado).delete()
                    for p in doc.get('praias', []):
                        pid = p.get('id')
                        if pid:
                            ComunicadoPraia.objects.get_or_create(
                                comunicado=comunicado, praia_id=pid
                            )

                    # Equipes
                    ComunicadoEquipe.objects.filter(comunicado=comunicado).delete()
                    for e in doc.get('equipes', []):
                        eid = e.get('id')
                        if eid:
                            ComunicadoEquipe.objects.get_or_create(
                                comunicado=comunicado, equipe_id=eid
                            )

                    # Ações
                    ComunicadoAcao.objects.filter(comunicado=comunicado).delete()
                    for a in doc.get('acoes', []):
                        aid = a.get('id')
                        if aid:
                            from acao.models import Acao
                            if Acao.objects.filter(pk=aid).exists():
                                ComunicadoAcao.objects.get_or_create(
                                    comunicado=comunicado, acao_id=aid
                                )

                    # Doações
                    ComunicadoDoacao.objects.filter(comunicado=comunicado).delete()
                    for d in doc.get('doacoes', []):
                        did = d.get('id')
                        if did:
                            from doacao.models import Doacao
                            if Doacao.objects.filter(pk=did).exists():
                                ComunicadoDoacao.objects.get_or_create(
                                    comunicado=comunicado, doacao_id=did
                                )

                    restaurados += 1
                    self.stdout.write(f'  [{prefixo}] Comunicado #{id_sql}: "{doc.get("titulo", "")}"')

            except Exception as e:
                erros += 1
                self.stdout.write(self.style.ERROR(f'  [ERRO] Comunicado #{id_sql}: {e}'))

        self.stdout.write(self.style.SUCCESS(
            f'[Comunicados] {restaurados} restaurados, {erros} erros.'
        ))

    # ──────────────────────────────────────────────────────────────────────────
    # CONDOMÍNIOS
    # ──────────────────────────────────────────────────────────────────────────

    def _restaurar_condominios(self):
        from condominio.models import Condominio, Bag, MovimentacaoBag
        from usuario.models import Usuario

        db = get_mongo_db()
        colecao = db['condominios']
        docs = list(colecao.find({}))

        self.stdout.write(f'\n[Condomínios] {len(docs)} documentos encontrados no MongoDB.')
        if not docs:
            return

        restaurados = 0
        erros = 0

        for doc in docs:
            id_sql = doc.get('id_sql')
            if not id_sql:
                continue

            try:
                with transaction.atomic():
                    praia_doc = doc.get('praia') or {}
                    praia_id = praia_doc.get('id') if praia_doc else None

                    end = doc.get('endereco') or {}
                    resp = doc.get('responsavel') or {}

                    condominio, criado = Condominio.objects.update_or_create(
                        id_condominio=id_sql,
                        defaults={
                            'nome': doc.get('nome', ''),
                            'responsavel_nome': resp.get('nome', ''),
                            'responsavel_telefone': resp.get('telefone', ''),
                            'responsavel_email': resp.get('email', ''),
                            'endereco': end.get('logradouro', ''),
                            'numero': end.get('numero', ''),
                            'complemento': end.get('complemento', ''),
                            'bairro': end.get('bairro', ''),
                            'cidade': end.get('cidade', ''),
                            'estado': end.get('estado', 'SP'),
                            'cep': end.get('cep', ''),
                            'porte': doc.get('porte', 'MEDIO'),
                            'confiabilidade': doc.get('confiabilidade', 'EM_AVALIACAO'),
                            'status': doc.get('status', 'ATIVO'),
                            'observacoes': doc.get('observacoes', ''),
                            'dt_cadastro': _dt(doc.get('dt_cadastro')) or datetime.now(),
                            'cadastrado_por_nome': doc.get('cadastrado_por_nome', ''),
                            'dt_ultima_edicao': _dt(doc.get('dt_ultima_edicao')),
                            'ultimo_editado_por_nome': doc.get('ultimo_editado_por_nome', ''),
                            'praia_id': praia_id,
                        },
                    )
                    prefixo = 'Criado' if criado else 'Atualizado'

                    # Bags embutidas no documento
                    for bag_doc in doc.get('bags', []):
                        bag_id = bag_doc.get('id') or bag_doc.get('id_bag')
                        if not bag_id:
                            continue
                        Bag.objects.update_or_create(
                            id_bag=bag_id,
                            defaults={
                                'condominio': condominio,
                                'codigo': bag_doc.get('codigo', f'BAG-{bag_id}'),
                                'status': bag_doc.get('status', 'DISPONIVEL'),
                                'peso_atual_kg': bag_doc.get('peso_atual_kg', 0),
                                'percentual_ocupacao': bag_doc.get('percentual_ocupacao', 0),
                                'observacoes': bag_doc.get('observacoes', ''),
                                'dt_cadastro': _dt(bag_doc.get('dt_cadastro')) or datetime.now(),
                                'cadastrado_por_nome': bag_doc.get('cadastrado_por_nome', ''),
                                'dt_ultima_edicao': _dt(bag_doc.get('dt_ultima_edicao')),
                                'ultimo_editado_por_nome': bag_doc.get('ultimo_editado_por_nome', ''),
                            },
                        )

                    restaurados += 1
                    self.stdout.write(f'  [{prefixo}] Condomínio #{id_sql}: "{doc.get("nome", "")}"')

            except Exception as e:
                erros += 1
                self.stdout.write(self.style.ERROR(f'  [ERRO] Condomínio #{id_sql}: {e}'))

        self.stdout.write(self.style.SUCCESS(
            f'[Condomínios] {restaurados} restaurados, {erros} erros.'
        ))

    # ──────────────────────────────────────────────────────────────────────────
    # AUDITORIA
    # ──────────────────────────────────────────────────────────────────────────

    def _restaurar_auditoria(self):
        from auditoria.models import EventoAuditoria
        from usuario.models import Usuario

        db = get_mongo_db()
        colecao = db['auditoria_eventos']
        docs = list(colecao.find({}).sort('data_evento', 1))

        self.stdout.write(f'\n[Auditoria] {len(docs)} documentos encontrados no MongoDB.')
        if not docs:
            return

        restaurados = 0
        erros = 0

        # Limpa a tabela local antes de importar (evita duplicatas)
        EventoAuditoria.objects.all().delete()

        for doc in docs:
            try:
                # Usuario (opcional — pode não existir mais)
                usuario_id = (doc.get('usuario') or {}).get('id')
                usuario = Usuario.objects.filter(pk=usuario_id).first() if usuario_id else None

                EventoAuditoria.objects.create(
                    entidade=doc.get('entidade', ''),
                    id_registro=doc.get('id_registro'),
                    acao=doc.get('acao', 'CRIACAO'),
                    usuario=usuario,
                    usuario_nome=doc.get('usuario_nome', '')[:150],
                    data_evento=_dt(doc.get('data_evento')) or datetime.now(),
                    resumo=doc.get('resumo', '')[:255],
                    valores_anteriores=doc.get('valores_anteriores', {}),
                    valores_novos=doc.get('valores_novos', {}),
                )
                restaurados += 1
            except Exception as e:
                erros += 1
                if erros <= 5:
                    self.stdout.write(self.style.ERROR(f'  [ERRO] {e}'))

        self.stdout.write(self.style.SUCCESS(
            f'[Auditoria] {restaurados} restaurados, {erros} erros.'
        ))
