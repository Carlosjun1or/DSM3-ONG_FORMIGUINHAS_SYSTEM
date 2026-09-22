from django import forms
from django.contrib.auth.models import User
from .models import Material, Movimentacao

# Formulário para cadastro de materiais
class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = ['nome', 'codigo', 'descricao', 'quantidade_inicial', 'unidade']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'quantidade_inicial': forms.NumberInput(attrs={'class': 'form-control'}),
            'unidade': forms.TextInput(attrs={'class': 'form-control'}),
        }

# Formulário para movimentações de estoque
class MovimentacaoForm(forms.ModelForm):
    class Meta:
        model = Movimentacao
        fields = ['material', 'tipo', 'quantidade']
        widgets = {
            'material': forms.Select(attrs={'class': 'form-control'}),
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'quantidade': forms.NumberInput(attrs={'class': 'form-control'}),
        }

# Formulário para cadastro de usuários
class UsuarioForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ['username', 'email', 'password']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }
