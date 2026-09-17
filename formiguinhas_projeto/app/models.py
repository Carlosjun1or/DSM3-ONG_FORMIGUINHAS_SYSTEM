from django.db import models
from django.contrib.auth.hashers import make_password, check_password

# Create your models here.

class Voluntario(models.Model):
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
    
    class Meta:
        db_table = 'voluntario'
        verbose_name = 'Voluntário'
        verbose_name_plural = 'Voluntários'
    
    def __str__(self):
        return self.nome
 
 
class Usuario(models.Model):
    TIPO_CHOICES = [
        ('ADMIN', 'Administrador'),
        ('COORDENADOR', 'Coordenador'),
    ]
    
    id_usuario = models.AutoField(primary_key=True)
    id_voluntario = models.OneToOneField(Voluntario, on_delete=models.CASCADE, related_name='usuario')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    senha = models.CharField(max_length=255)
    data_ultimo_acesso = models.DateTimeField(null=True, blank=True)
    
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
    
    