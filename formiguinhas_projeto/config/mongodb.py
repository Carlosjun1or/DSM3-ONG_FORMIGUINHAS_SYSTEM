"""
Conector e utilitários para MongoDB Atlas (Persistência Poliglota - Cenário C).
Fornece gerenciamento seguro de conexões, cache de conectividade e tolerância a falhas.
"""
import logging
import sys
import time
from django.conf import settings
from pymongo import MongoClient
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError

logger = logging.getLogger(__name__)

_mongo_client = None
_last_check_time = 0
_last_check_result = None
CACHE_TTL_SEGUNDOS = 15  # Evita re-testar handshake a cada requisição HTTP quando offline


def _em_modo_teste():
    """Detecta se o Django está executando em suíte de testes (manage.py test)."""
    return 'test' in sys.argv or getattr(settings, 'TESTING', False)


def get_mongo_client():
    """
    Retorna a instância singleton do cliente MongoClient.
    Reutiliza a conexão para eficiência e gerenciamento de pool.
    """
    global _mongo_client
    if _em_modo_teste():
        return None

    if _mongo_client is not None:
        return _mongo_client

    uri = getattr(settings, 'MONGODB_URI', '')
    if not uri:
        return None

    timeout_ms = getattr(settings, 'MONGODB_TIMEOUT_MS', 3000)
    try:
        # Importa certifi se disponível para certificados SSL atualizados
        tls_kwargs = {}
        try:
            import certifi
            tls_kwargs['tlsCAFile'] = certifi.where()
        except ImportError:
            pass

        _mongo_client = MongoClient(
            uri,
            serverSelectionTimeoutMS=timeout_ms,
            connectTimeoutMS=timeout_ms,
            socketTimeoutMS=timeout_ms,
            retryWrites=True,
            appname='FormiguinhasSystem',
            **tls_kwargs,
        )
        return _mongo_client
    except Exception as erro:
        logger.warning(f'Erro ao inicializar cliente MongoDB: {erro}')
        _mongo_client = None
        return None


def get_mongo_db():
    """Retorna a instância do banco de dados MongoDB configurado."""
    if _em_modo_teste():
        return None

    cliente = get_mongo_client()
    if cliente is None:
        return None

    nome_banco = getattr(settings, 'MONGODB_DATABASE', 'formiguinhas_db')
    try:
        return cliente[nome_banco]
    except Exception as erro:
        logger.warning(f'Erro ao obter database {nome_banco}: {erro}')
        return None


def get_mongo_collection(nome_colecao):
    """Retorna uma collection do MongoDB Atlas ou None se indisponível."""
    db = get_mongo_db()
    if db is None:
        return None
    try:
        return db[nome_colecao]
    except Exception as erro:
        logger.warning(f'Erro ao acessar collection {nome_colecao}: {erro}')
        return None


def test_mongo_connection(forcar=False):
    """
    Testa a conectividade com o MongoDB Atlas com cache de 15 segundos para performance.
    Retorna uma tupla (sucesso: bool, mensagem: str, info: dict).
    """
    global _last_check_time, _last_check_result

    if _em_modo_teste():
        return False, 'Modo de testes ativo (MongoDB desabilitado para testes unitários).', {}

    agora = time.time()
    if not forcar and _last_check_result is not None and (agora - _last_check_time) < CACHE_TTL_SEGUNDOS:
        return _last_check_result

    uri = getattr(settings, 'MONGODB_URI', '')
    if not uri:
        res = (False, 'MONGODB_URI não configurada.', {})
        _last_check_time = agora
        _last_check_result = res
        return res

    try:
        cliente = get_mongo_client()
        if cliente is None:
            res = (False, 'Não foi possível instanciar o cliente MongoDB.', {})
            _last_check_time = agora
            _last_check_result = res
            return res

        cliente.admin.command('ping')
        nome_banco = getattr(settings, 'MONGODB_DATABASE', 'formiguinhas_db')
        db = cliente[nome_banco]
        colecoes = db.list_collection_names()

        res = (True, 'Conexão com MongoDB Atlas estabelecida com sucesso.', {
            'banco': nome_banco,
            'colecoes': colecoes,
        })
        _last_check_time = agora
        _last_check_result = res
        return res
    except (ServerSelectionTimeoutError, PyMongoError) as erro:
        erro_str = str(erro)
        if 'TLSV1_ALERT_INTERNAL_ERROR' in erro_str or 'SSL handshake failed' in erro_str:
            ip_atual = 'desconhecido'
            try:
                import urllib.request
                ip_atual = urllib.request.urlopen('https://api.ipify.org', timeout=2).read().decode('utf-8')
            except Exception:
                pass
            msg = (
                f'O cluster MongoDB Atlas recusou a conexão SSL (TLSV1_ALERT_INTERNAL_ERROR).\n'
                f'-> Causa: O seu endereço IP público atual ({ip_atual}) NÃO está liberado na lista de acesso do MongoDB Atlas.\n'
                f'-> Solução:\n'
                f'   1. Acesse https://cloud.mongodb.com e entre na sua conta.\n'
                f'   2. No menu lateral esquerdo, vá em "Security" -> "Network Access".\n'
                f'   3. Clique no botão verde "+ Add IP Address".\n'
                f'   4. Clique em "Allow Access from Anywhere" (0.0.0.0/0) ou "Add Current IP Address" ({ip_atual}).\n'
                f'   5. Clique em "Confirm" e aguarde cerca de 1 minuto até o status ficar verde ("Active").'
            )
            res = (False, msg, {'ip_atual': ip_atual, 'erro_tipo': 'IP_NAO_LIBERADO'})
        else:
            res = (False, f'Não foi possível comunicar com o cluster MongoDB Atlas: {erro}', {})
        _last_check_time = agora
        _last_check_result = res
        return res
    except Exception as erro:
        res = (False, f'Erro inesperado na conexão MongoDB: {erro}', {})
        _last_check_time = agora
        _last_check_result = res
        return res


def close_mongo_client():
    """Fecha a conexão do cliente MongoDB se estiver aberto."""
    global _mongo_client, _last_check_result
    if _mongo_client is not None:
        try:
            _mongo_client.close()
        except Exception:
            pass
        _mongo_client = None
    _last_check_result = None


class MongoDictProxy:
    """
    Proxy transparente para documentos/dicionários retornados do MongoDB Atlas,
    permitindo acesso tanto por atributo (.campo) quanto por chave (['campo']).
    """
    def __init__(self, data=None):
        self._data = data if isinstance(data, dict) else {}

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        if name in self._data:
            val = self._data[name]
            if isinstance(val, dict):
                return MongoDictProxy(val)
            return val
        return None

    def __getitem__(self, key):
        return self._data[key]

    def __contains__(self, key):
        return key in self._data

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __bool__(self):
        return bool(self._data)


class MongoAcaoProxy(MongoDictProxy):
    """Proxy para documentos de Ação oriundos do MongoDB Atlas."""
    @property
    def pk(self):
        return self._data.get('id_sql') or self._data.get('id')

    @property
    def id_acao(self):
        return self.pk

    @property
    def praia_id(self):
        praia = self._data.get('praia')
        if isinstance(praia, dict):
            return praia.get('id') or praia.get('id_praia')
        return None

    @property
    def praia(self):
        praia = self._data.get('praia')
        if isinstance(praia, dict):
            return MongoDictProxy(praia)
        return None

    def get_tipo_display(self):
        m = {
            'LIMPEZA': 'Limpeza de Praia',
            'MUTIRAO': 'Mutirão de Limpeza',
            'SENSIBILIZACAO': 'Sensibilização',
            'TRIAGEM': 'Triagem',
            'OUTRO': 'Outro',
        }
        tipo = self._data.get('tipo', '')
        return m.get(tipo, tipo)

    def get_status_display(self):
        m = {
            'PLANEJADA': 'Planejada',
            'EM_ANDAMENTO': 'Em Andamento',
            'CONCLUIDA': 'Concluída',
            'CANCELADA': 'Cancelada',
        }
        status = self._data.get('status', '')
        return m.get(status, status)

    def __str__(self):
        praia = self._data.get('praia') or {}
        praia_nome = praia.get('nome') if isinstance(praia, dict) else ''
        data = self._data.get('data') or ''
        tipo = self.get_tipo_display()
        partes = [tipo]
        if praia_nome:
            partes.append(praia_nome)
        if data:
            partes.append(f"({data})")
        return ' - '.join(partes) or f"Ação #{self.pk}"


class MongoBagProxy(MongoDictProxy):
    """Proxy para documentos de Bag oriundos do MongoDB Atlas."""
    @property
    def pk(self):
        return self._data.get('id') or self._data.get('id_sql')

    @property
    def id_bag(self):
        return self.pk

    @property
    def codigo(self):
        return self._data.get('codigo', f'Bag #{self.pk}')

    @property
    def condominio(self):
        cond = self._data.get('condominio')
        if isinstance(cond, dict):
            return MongoDictProxy(cond)
        # Se veio de busca em condominio
        if 'condominio_nome' in self._data:
            return MongoDictProxy({
                'id': self._data.get('condominio_id'),
                'nome': self._data.get('condominio_nome'),
                'praia': self._data.get('condominio_praia'),
            })
        return None

    def get_status_display(self):
        m = {
            'DISPONIVEL': 'Disponível',
            'EM_USO': 'Em uso',
            'CHEIA': 'Cheia',
            'DANIFICADA': 'Danificada',
        }
        status = self._data.get('status', '')
        return m.get(status, status)

    def __str__(self):
        return f"Bag {self.codigo}"


# Aliases de compatibilidade para scripts e serviços utilitários
get_db = get_mongo_db
get_client = get_mongo_client



