from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone

# Create your models here.

class Voluntario(models.Model):
    """Pessoa cadastrada na ONG (não necessariamente com acesso ao sistema).
    
    Diferente de Usuario (que é quem faz login), o Voluntario é o perfil pessoal:
    nome, contato, data de nascimento, status (ativo/inativo/pausado).
    O relacionamento Voluntario 1:1 Usuario é opcional — nem todo voluntário tem login.
    """
    STATUS_CHOICES = [
        ('ATIVO', 'Ativo'),
        ('INATIVO', 'Inativo'),
        ('PAUSADO', 'Pausado'),
    ]
    
    id_voluntario = models.AutoField(primary_key=True)
    nome = models.CharField(max_length=150)
    dt_nascimento = models.DateField()
    endereco = models.CharField(max_length=255)
    telefone = models.CharField(max_length=15)
    email = models.EmailField(unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ATIVO')
    dt_cadastro = models.DateTimeField(auto_now_add=True)
    cadastrado_por = models.ForeignKey(
        'Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='voluntarios_cadastrados',
    )
    cadastrado_por_nome = models.CharField(max_length=150, null=True, blank=True)
    cadastrado_por_tipo = models.CharField(max_length=20, null=True, blank=True)
    ultimo_editado_por = models.ForeignKey(
        'Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='voluntarios_editados',
    )
    ultimo_editado_por_nome = models.CharField(max_length=150, null=True, blank=True)
    ultimo_editado_por_tipo = models.CharField(max_length=20, null=True, blank=True)
    dt_ultima_edicao = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'voluntario'
        verbose_name = 'Voluntário'
        verbose_name_plural = 'Voluntários'
    
    def __str__(self):
        return self.nome

    @property
    def idade(self):
        """Calcula idade considerando se o aniversário já ocorreu no ano corrente."""
        hoje = timezone.localdate()
        idade = hoje.year - self.dt_nascimento.year
        aniversario_ainda_nao_chegou = (hoje.month, hoje.day) < (
            self.dt_nascimento.month,
            self.dt_nascimento.day,
        )
        return idade - int(aniversario_ainda_nao_chegou)
 
 
class Usuario(models.Model):
    """Credencial de acesso ao sistema (login por sessão, não Django auth.User).
    
    Vincula-se 1:1 a um Voluntario. A senha é hasheada com make_password/check_password
    do Django, mas a autenticação é manual (session-based, sem usar contrib.auth).
    Tipos: ADMIN (acesso total) ou COORDENADOR (acesso restrito a suas ações).
    """
    TIPO_CHOICES = [
        ('ADMIN', 'Administrador'),
        ('COORDENADOR', 'Coordenador'),
    ]
    
    id_usuario = models.AutoField(primary_key=True)
    id_voluntario = models.OneToOneField(Voluntario, on_delete=models.CASCADE, related_name='usuario')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    senha = models.CharField(max_length=255)
    data_ultimo_acesso = models.DateTimeField(null=True, blank=True)
    dt_cadastro = models.DateTimeField(
        default=timezone.now,
        null=True,
    )
    cadastrado_por = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='usuarios_cadastrados',
    )
    cadastrado_por_nome = models.CharField(max_length=150, null=True, blank=True)
    cadastrado_por_tipo = models.CharField(max_length=20, null=True, blank=True)
    ultimo_editado_por = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='usuarios_editados',
    )
    ultimo_editado_por_nome = models.CharField(max_length=150, null=True, blank=True)
    ultimo_editado_por_tipo = models.CharField(max_length=20, null=True, blank=True)
    dt_ultima_edicao = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'usuario'
        verbose_name = 'Usuário'
        verbose_name_plural = 'Usuários'
    
    def __str__(self):
        return f"{self.id_voluntario.nome} ({self.get_tipo_display()})"
    
    def set_password(self, password):
        self.senha = make_password(password)
    
    def check_password(self, password):
        return check_password(password, self.senha)
    
    