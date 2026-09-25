from django import forms
from django.contrib.auth.models import User
from .models import Material, Movimentacao

# Formulário para cadastro de materiais
class MaterialForm(forms.ModelForm):
    unidade = forms.ChoiceField(
        choices=[('', 'Selecione uma opção')] + Material.UNIDADES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    class Meta:
        model = Material
        fields = [
            'nome',
            'codigo',
            'descricao',
            'quantidade_inicial',
            'unidade',
            'is_donativo',
            'doador'
        ]

        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'quantidade_inicial': forms.NumberInput(attrs={'class': 'form-control'}),
            'unidade': forms.Select(attrs={'class': 'form-control'}),  # ✅ corrigido
            'is_donativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'doador': forms.TextInput(attrs={'class': 'form-control'}),
        }
class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = [
            'nome',
            'codigo',
            'descricao',
            'quantidade_inicial',
            'unidade',
            'is_donativo',
            'doador'
        ]

        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'quantidade_inicial': forms.NumberInput(attrs={'class': 'form-control'}),
            'unidade': forms.Select(attrs={'class': 'form-control'}),  # ✅ corrigido
            'is_donativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'doador': forms.TextInput(attrs={'class': 'form-control'}),
        }


        

    def clean_codigo(self):
        codigo = self.cleaned_data['codigo']
        if Material.objects.filter(codigo=codigo).exists():
            raise forms.ValidationError("Já existe um material com este código.")
        return codigo


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

    def clean(self):
        cleaned_data = super().clean()
        material = cleaned_data.get('material')
        tipo = cleaned_data.get('tipo')
        quantidade = cleaned_data.get('quantidade')

        if material and tipo == 'saida' and quantidade:
            if quantidade > material.saldo:
                raise forms.ValidationError("Movimentação inválida: saldo insuficiente.")
        return cleaned_data


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

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Este nome de usuário já está em uso.")
        return username

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Já existe um usuário com este e-mail.")
        return email
