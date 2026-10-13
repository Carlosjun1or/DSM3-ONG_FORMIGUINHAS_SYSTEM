from django import forms

from .models import Usuario, Voluntario


class LoginForm(forms.Form):
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={
            'class': 'form-control email-input',
            'placeholder': 'seu@email.com',
            'autocomplete': 'email',
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
