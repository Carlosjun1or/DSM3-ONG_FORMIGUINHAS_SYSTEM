from django import forms
from django.utils import timezone
from .models import Usuario, Voluntario


def validar_maioridade(data_nascimento):
    hoje = timezone.localdate()
    if data_nascimento > hoje:
        raise forms.ValidationError('A data de nascimento não pode ser futura.')

    idade = hoje.year - data_nascimento.year
    aniversario_ainda_nao_chegou = (hoje.month, hoje.day) < (
        data_nascimento.month,
        data_nascimento.day,
    )
    idade -= int(aniversario_ainda_nao_chegou)

    if idade < 18:
        raise forms.ValidationError(
            'O voluntário precisa ter 18 anos ou mais para ser responsável.'
        )

    return data_nascimento


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


class VoluntarioForm(forms.ModelForm):
    dt_nascimento = forms.DateField(
        label='Data de nascimento',
        input_formats=['%d/%m/%Y', '%Y-%m-%d'],
        widget=forms.DateInput(format='%d/%m/%Y', attrs={
            'class': 'form-control data-nascimento-input',
            'inputmode': 'numeric',
            'maxlength': '10',
            'placeholder': 'dd/mm/aaaa',
            'type': 'text',
        })
    )

    class Meta:
        model = Voluntario
        fields = ['nome', 'dt_nascimento', 'endereco', 'telefone', 'email']
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Digite o nome completo',
            }),
            'endereco': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Rua, número, bairro e cidade',
            }),
            'telefone': forms.TextInput(attrs={
                'class': 'form-control telefone-input',
                'inputmode': 'numeric',
                'maxlength': '15',
                'placeholder': '(11) 99999-9999',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control email-input',
                'inputmode': 'email',
                'autocomplete': 'email',
                'placeholder': 'seu@email.com',
            }),
        }

    def clean_dt_nascimento(self):
        return validar_maioridade(self.cleaned_data['dt_nascimento'])


class VoluntarioEdicaoForm(VoluntarioForm):
    status = forms.ChoiceField(
        label='Status',
        choices=Voluntario.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta(VoluntarioForm.Meta):
        fields = VoluntarioForm.Meta.fields + ['status']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and hasattr(self.instance, 'usuario') and self.instance.usuario.tipo == 'ADMIN':
            self.fields['status'].choices = [('ATIVO', 'Ativo')]

    def clean_status(self):
        status = self.cleaned_data['status']
        if hasattr(self.instance, 'usuario') and self.instance.usuario.tipo == 'ADMIN' and status != 'ATIVO':
            raise forms.ValidationError(
                'O voluntário administrador precisa permanecer com status Ativo.'
            )
        return status


class UsuarioForm(forms.Form):
    voluntario = forms.ModelChoiceField(
        label='Voluntário',
        queryset=Voluntario.objects.all().order_by('nome'),
        empty_label='Selecione um voluntário',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    tipo = forms.ChoiceField(
        label='Tipo do usuário',
        choices=Usuario.TIPO_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    senha = forms.CharField(
        label='Senha',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Digite uma senha',
        })
    )
    confirmar_senha = forms.CharField(
        label='Confirmar senha',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Repita a senha',
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['voluntario'].label_from_instance = (
            lambda voluntario: f'{voluntario.nome} - {voluntario.email}'
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
        if voluntario:
            possui_usuario = Usuario.objects.filter(
                id_voluntario=voluntario
            ).exists()
            possui_usuario_pelo_email = Usuario.objects.filter(
                id_voluntario__email__iexact=voluntario.email
            ).exists()

            if possui_usuario or possui_usuario_pelo_email:
                raise forms.ValidationError(
                    f'O e-mail {voluntario.email} já possui um usuário cadastrado.'
                )
        return voluntario


class UsuarioEdicaoForm(forms.Form):
    tipo = forms.ChoiceField(
        label='Tipo de usuário',
        choices=Usuario.TIPO_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class PerfilForm(forms.ModelForm):
    dt_nascimento = forms.DateField(
        label='Data de nascimento',
        input_formats=['%d/%m/%Y', '%Y-%m-%d'],
        widget=forms.DateInput(format='%d/%m/%Y', attrs={
            'class': 'form-control data-nascimento-input',
            'inputmode': 'numeric',
            'maxlength': '10',
            'placeholder': 'dd/mm/aaaa',
            'type': 'text',
        })
    )

    class Meta:
        model = Voluntario
        fields = ['nome', 'dt_nascimento', 'endereco', 'telefone', 'email']
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Digite o nome completo',
            }),
            'endereco': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Rua, número, bairro e cidade',
            }),
            'telefone': forms.TextInput(attrs={
                'class': 'form-control telefone-input',
                'inputmode': 'numeric',
                'maxlength': '15',
                'placeholder': '(11) 99999-9999',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control email-input',
                'inputmode': 'email',
                'autocomplete': 'email',
                'placeholder': 'seu@email.com',
            }),
        }


class CadastroForm(forms.Form):
    nome = forms.CharField(label='Nome', max_length=150, widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Digite o nome completo',
    }))
    dt_nascimento = forms.DateField(
        label='Data de nascimento',
        input_formats=['%d/%m/%Y', '%Y-%m-%d'],
        widget=forms.DateInput(format='%d/%m/%Y', attrs={
            'class': 'form-control data-nascimento-input',
            'inputmode': 'numeric',
            'maxlength': '10',
            'placeholder': 'dd/mm/aaaa',
            'type': 'text',
        })
    )
    endereco = forms.CharField(label='Endereço', max_length=255, widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Rua, número, bairro e cidade',
    }))
    telefone = forms.CharField(label='Telefone', max_length=15, widget=forms.TextInput(attrs={
        'class': 'form-control telefone-input',
        'inputmode': 'numeric',
        'maxlength': '15',
        'placeholder': '(11) 99999-9999',
    }))
    email = forms.EmailField(label='Email', widget=forms.EmailInput(attrs={
        'class': 'form-control email-input',
        'inputmode': 'email',
        'autocomplete': 'email',
        'placeholder': 'seu@email.com',
    }))
    tipo = forms.ChoiceField(label='Tipo do usuário', choices=Usuario.TIPO_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}))
    senha = forms.CharField(label='Senha', widget=forms.PasswordInput(attrs={
        'class': 'form-control',
        'placeholder': 'Digite uma senha',
    }))
    confirmar_senha = forms.CharField(label='Confirmar senha', widget=forms.PasswordInput(attrs={
        'class': 'form-control',
        'placeholder': 'Repita a senha',
    }))

    def clean_dt_nascimento(self):
        return validar_maioridade(self.cleaned_data['dt_nascimento'])

    def clean(self):
        cleaned = super().clean()
        senha = cleaned.get('senha')
        confirmar_senha = cleaned.get('confirmar_senha')

        if senha and confirmar_senha and senha != confirmar_senha:
            self.add_error('confirmar_senha', 'As senhas não coincidem.')

        return cleaned

    def save(self, cadastrado_por=None):
        cadastrado_por_nome = cadastrado_por.id_voluntario.nome if cadastrado_por else None
        cadastrado_por_tipo = cadastrado_por.tipo if cadastrado_por else None
        voluntario = Voluntario.objects.create(
            nome=self.cleaned_data['nome'],
            dt_nascimento=self.cleaned_data['dt_nascimento'],
            endereco=self.cleaned_data['endereco'],
            telefone=self.cleaned_data['telefone'],
            email=self.cleaned_data['email'],
            status='ATIVO',
            cadastrado_por=cadastrado_por,
            cadastrado_por_nome=cadastrado_por_nome,
            cadastrado_por_tipo=cadastrado_por_tipo,
        )
        usuario = Usuario.objects.create(
            id_voluntario=voluntario,
            tipo=self.cleaned_data['tipo'],
            cadastrado_por=cadastrado_por,
            cadastrado_por_nome=cadastrado_por_nome,
            cadastrado_por_tipo=cadastrado_por_tipo,
        )
        usuario.set_password(self.cleaned_data['senha'])
        usuario.save()
        return voluntario, usuario