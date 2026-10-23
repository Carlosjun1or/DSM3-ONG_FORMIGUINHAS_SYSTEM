from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Tema(models.Model):
    nome = models.CharField(max_length=120, unique=True)
    descricao = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)
    criado_por = models.ForeignKey('usuario.Usuario', on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='temas_criados')
    atualizado_por = models.ForeignKey('usuario.Usuario', on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='temas_atualizados')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'comunicado_tema'
        ordering = ('nome',)

    def __str__(self):
        return self.nome


class Comunicado(models.Model):
    """
    Aviso ou notícia criada pelos admins para os coordenadores/voluntários.
    
    Regras de negócio (validadas em clean()):
    - NOTICIA: sempre pública (TODOS) e obrigatoriamente tem Tema.
    - AVISO: nunca tem Tema; pode ser TODOS ou só COORDENADORES.
    - dt_expiracao deve ser posterior à dt_publicacao.
    - duracao_expiracao e unidade_duracao_expiracao são dependentes (ambos ou nenhum).
    
    O ciclo de vida (RASCUNHO → PUBLICADO → ARQUIVADO) é gerenciado pelo services.py.
    """
    AVISO = 'AVISO'
    NOTICIA = 'NOTICIA'
    TIPO_CHOICES = [(AVISO, 'Aviso'), (NOTICIA, 'Notícia')]
    TODOS = 'TODOS'
    COORDENADORES = 'COORDENADORES'
    PUBLICO_CHOICES = [(TODOS, 'Todos'), (COORDENADORES, 'Só coordenadores')]
    RASCUNHO = 'RASCUNHO'
    PUBLICADO = 'PUBLICADO'
    ARQUIVADO = 'ARQUIVADO'
    STATUS_CHOICES = [(RASCUNHO, 'Rascunho'), (PUBLICADO, 'Publicado'), (ARQUIVADO, 'Arquivado')]
    UNIDADE_DURACAO_CHOICES = [
        ('DIAS', 'dias'),
        ('SEMANAS', 'semanas'),
        ('MESES', 'meses'),
        ('ANOS', 'anos'),
    ]

    id_comunicado = models.AutoField(primary_key=True)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    titulo = models.CharField(max_length=200)
    resumo = models.CharField(max_length=500, blank=True)
    conteudo = models.TextField()
    publico = models.CharField(max_length=15, choices=PUBLICO_CHOICES, default=TODOS)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=RASCUNHO)
    tema = models.ForeignKey(Tema, on_delete=models.PROTECT, null=True, blank=True, related_name='noticias')
    dt_publicacao = models.DateTimeField(null=True, blank=True)
    dt_expiracao = models.DateTimeField(null=True, blank=True)
    duracao_expiracao = models.PositiveIntegerField(null=True, blank=True)
    unidade_duracao_expiracao = models.CharField(
        max_length=10,
        choices=UNIDADE_DURACAO_CHOICES,
        null=True,
        blank=True,
    )
    autor = models.ForeignKey('usuario.Usuario', on_delete=models.SET_NULL, null=True, related_name='comunicados_criados')
    perfil_autor = models.CharField(max_length=20, blank=True)
    ultimo_editado_por = models.ForeignKey('usuario.Usuario', on_delete=models.SET_NULL, null=True, blank=True,
                                           related_name='comunicados_editados')
    dt_ultima_edicao = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'comunicado'
        ordering = ('-dt_publicacao', '-criado_em')
        indexes = [
            models.Index(fields=('status', 'publico', 'dt_publicacao')),
            models.Index(fields=('tipo', 'status')),
        ]

    def clean(self):
        errors = {}
        if self.tipo == self.NOTICIA:
            if self.publico != self.TODOS:
                errors['publico'] = 'Notícias são sempre públicas.'
            if not self.tema_id:
                errors['tema'] = 'Notícias precisam de um tema.'
        elif self.tipo == self.AVISO:
            if self.tema_id:
                errors['tema'] = 'Avisos não podem ter tema.'
            if self.publico not in dict(self.PUBLICO_CHOICES):
                errors['publico'] = 'Selecione um público válido.'
        if self.dt_publicacao and self.dt_expiracao and self.dt_expiracao <= self.dt_publicacao:
            errors['dt_expiracao'] = 'A expiração deve ser posterior à publicação.'
        if (self.duracao_expiracao is None) != (self.unidade_duracao_expiracao is None):
            errors['duracao_expiracao'] = 'Informe a quantidade e a unidade do prazo de expiração.'
        if self.duracao_expiracao is not None and self.duracao_expiracao <= 0:
            errors['duracao_expiracao'] = 'A quantidade do prazo deve ser maior que zero.'
        if errors:
            raise ValidationError(errors)

    def esta_vigente(self):
        agora = timezone.now()
        return (
            self.status == self.PUBLICADO
            and self.dt_publicacao is not None
            and self.dt_publicacao <= agora
            and (self.dt_expiracao is None or self.dt_expiracao > agora)
        )

    def __str__(self):
        return self.titulo


class ComunicadoPraia(models.Model):
    comunicado = models.ForeignKey(Comunicado, on_delete=models.CASCADE, related_name='praias')
    praia = models.ForeignKey('praia.Praia', on_delete=models.DO_NOTHING, db_constraint=False, related_name='comunicados')
    class Meta:
        managed = False
        db_table = 'comunicado_praia'
        constraints = [models.UniqueConstraint(fields=('comunicado', 'praia'), name='comunicado_praia_unico')]


class ComunicadoEquipe(models.Model):
    comunicado = models.ForeignKey(Comunicado, on_delete=models.CASCADE, related_name='equipes')
    equipe = models.ForeignKey('equipe.Equipe', on_delete=models.DO_NOTHING, db_constraint=False, related_name='comunicados')
    class Meta:
        managed = False
        db_table = 'comunicado_equipe'
        constraints = [models.UniqueConstraint(fields=('comunicado', 'equipe'), name='comunicado_equipe_unico')]


class ComunicadoAcao(models.Model):
    comunicado = models.ForeignKey(Comunicado, on_delete=models.CASCADE, related_name='acoes')
    acao = models.ForeignKey('acao.Acao', on_delete=models.DO_NOTHING, db_constraint=False, related_name='comunicados')
    class Meta:
        managed = False
        db_table = 'comunicado_acao'
        constraints = [models.UniqueConstraint(fields=('comunicado', 'acao'), name='comunicado_acao_unico')]


class ComunicadoDoacao(models.Model):
    comunicado = models.ForeignKey(Comunicado, on_delete=models.CASCADE, related_name='doacoes')
    doacao = models.ForeignKey('doacao.Doacao', on_delete=models.DO_NOTHING, db_constraint=False, related_name='comunicados')

    class Meta:
        managed = False
        db_table = 'comunicado_doacao'
        constraints = [
            models.UniqueConstraint(
                fields=('comunicado', 'doacao'),
                name='comunicado_doacao_unico',
            ),
        ]


class ComunicadoLeitura(models.Model):
    """Registro de que um usuário leu um comunicado (controle de não-lidos).
    
    A constraint UniqueConstraint impede duplicar a leitura do mesmo comunicado.
    O context_processors.py consulta essa tabela (ou o MongoDB) para contar
    quantos comunicados vigentes o usuário ainda não leu.
    """
    comunicado = models.ForeignKey(
        Comunicado,
        on_delete=models.CASCADE,
        related_name='leituras',
    )
    usuario = models.ForeignKey(
        'usuario.Usuario',
        on_delete=models.CASCADE,
        related_name='leituras_comunicados',
    )
    lido_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'comunicado_leitura'
        constraints = [
            models.UniqueConstraint(
                fields=('comunicado', 'usuario'),
                name='comunicado_leitura_unica',
            ),
        ]
        indexes = [
            models.Index(fields=('usuario', 'lido_em')),
        ]
