from django import forms
from .models import Usuario, Voluntario


class LoginForm(forms.Form):
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'seu@email.com'
        })
    )
    senha = forms.CharField(
        label='Senha',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Digite sua senha'
        })
    )

    def clean(self):
        email = self.cleaned_data.get('email')
        senha = self.cleaned_data.get('senha')

        if email and senha:
            try:
                voluntario = Voluntario.objects.get(email=email)
                usuario = Usuario.objects.get(id_voluntario=voluntario)

                if not usuario.check_password(senha):
                    raise forms.ValidationError('Email ou senha incorretos')

                if voluntario.status != 'ATIVO':
                    raise forms.ValidationError('Usuário inativo')

                self.usuario = usuario
            except (Voluntario.DoesNotExist, Usuario.DoesNotExist):
                raise forms.ValidationError('Email ou senha incorretos')

        return self.cleaned_data


class VoluntarioForm(forms.ModelForm):
    class Meta:
        model = Voluntario
        fields = ['nome', 'dt_nascimento', 'endereco', 'telefone', 'email']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'dt_nascimento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'endereco': forms.TextInput(attrs={'class': 'form-control'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }


class UsuarioForm(forms.Form):
    voluntario = forms.ModelChoiceField(
        label='Voluntário',
        queryset=Voluntario.objects.all().order_by('nome'),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    tipo = forms.ChoiceField(
        label='Tipo do usuário',
        choices=Usuario.TIPO_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    senha = forms.CharField(
        label='Senha',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    confirmar_senha = forms.CharField(
        label='Confirmar senha',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    def clean(self):
        cleaned = super().clean()
        senha = cleaned.get('senha')
        confirmar_senha = cleaned.get('confirmar_senha')

        if senha and confirmar_senha and senha != confirmar_senha:
            self.add_error('confirmar_senha', 'As senhas não coincidem.')

        return cleaned

    def clean_voluntario(self):
        voluntario = self.cleaned_data.get('voluntario')
        if voluntario and Usuario.objects.filter(id_voluntario=voluntario).exists():
            raise forms.ValidationError('Esse voluntário já possui um usuário cadastrado.')
        return voluntario


class PerfilForm(forms.ModelForm):
    class Meta:
        model = Voluntario
        fields = ['nome', 'dt_nascimento', 'endereco', 'telefone', 'email']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'dt_nascimento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'endereco': forms.TextInput(attrs={'class': 'form-control'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }


class CadastroForm(forms.Form):
    nome = forms.CharField(label='Nome', max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))
    dt_nascimento = forms.DateField(label='Data de nascimento', widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}))
    endereco = forms.CharField(label='Endereço', max_length=255, widget=forms.TextInput(attrs={'class': 'form-control'}))
    telefone = forms.CharField(label='Telefone', max_length=15, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(label='Email', widget=forms.EmailInput(attrs={'class': 'form-control'}))
    tipo = forms.ChoiceField(label='Tipo do usuário', choices=Usuario.TIPO_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}))
    senha = forms.CharField(label='Senha', widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    confirmar_senha = forms.CharField(label='Confirmar senha', widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    def clean(self):
        cleaned = super().clean()
        senha = cleaned.get('senha')
        confirmar_senha = cleaned.get('confirmar_senha')

        if senha and confirmar_senha and senha != confirmar_senha:
            self.add_error('confirmar_senha', 'As senhas não coincidem.')

        return cleaned

    def save(self):
        voluntario = Voluntario.objects.create(
            nome=self.cleaned_data['nome'],
            dt_nascimento=self.cleaned_data['dt_nascimento'],
            endereco=self.cleaned_data['endereco'],
            telefone=self.cleaned_data['telefone'],
            email=self.cleaned_data['email'],
            status='ATIVO'
        )
        usuario = Usuario.objects.create(
            id_voluntario=voluntario,
            tipo=self.cleaned_data['tipo']
        )
        usuario.set_password(self.cleaned_data['senha'])
        usuario.save()
        return voluntario, usuario