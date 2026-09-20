from django import forms
from django.db.models import Q
from PIL import Image

from praia.models import Praia
from usuario.models import Voluntario

from .models import (
    Acao,
    AcaoImagem,
    AcaoParticipante,
    AcaoParticipanteHistorico,
    AcaoResponsavel,
)

MAX_IMAGE_SIZE = 5 * 1024 * 1024


class AcaoForm(forms.ModelForm):
    data = forms.DateField(
        label='Data',
        input_formats=['%d/%m/%Y', '%Y-%m-%d'],
        widget=forms.DateInput(format='%d/%m/%Y', attrs={
            'class': 'form-control acao-data-input',
            'inputmode': 'numeric',
            'maxlength': '10',
            'placeholder': 'dd/mm/aaaa',
            'type': 'text',
        }),
    )
    horario = forms.TimeField(
        label='Horário',
        input_formats=['%H:%M'],
        required=False,
        widget=forms.TimeInput(format='%H:%M', attrs={
            'class': 'form-control acao-horario-input',
            'inputmode': 'numeric',
            'maxlength': '5',
            'placeholder': 'hh:mm',
            'type': 'text',
        }),
    )

    class Meta:
        model = Acao
        fields = ['tipo', 'praia', 'data', 'horario', 'local', 'descricao', 'status']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'praia': forms.Select(attrs={'class': 'form-control'}),
            'local': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Local da ação'}),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Descreva como será realizada a ação',
            }),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['local'].label = 'Ponto de encontro'
        self.fields['local'].help_text = (
            'Informe o ponto específico dentro da praia, como quiosque, '
            'entrada ou posto dos guarda-vidas.'
        )
        self.fields['local'].widget.attrs.update({
            'placeholder': (
                'Ex.: Quiosque 12, acesso principal ou posto dos guarda-vidas'
            ),
        })
        self.fields['tipo'].choices = [
            ('', 'Selecione o tipo de ação'),
            *Acao.TIPO_CHOICES,
        ]

        praias_ativas = Praia.objects.filter(praia_ativa='ATIVA')
        if self.instance and self.instance.praia_id:
            praias_ativas = Praia.objects.filter(
                Q(praia_ativa='ATIVA') | Q(pk=self.instance.praia_id)
            )
        self.fields['praia'].queryset = praias_ativas
        self.fields['praia'].empty_label = 'Selecione a praia da ação'
        self.fields['praia'].label_from_instance = (
            lambda praia: f'{praia.nome} - {praia.cidade}'
        )


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.FileField):
    def clean(self, data, initial=None):
        if not data:
            raise forms.ValidationError('Selecione pelo menos uma imagem.')
        if not isinstance(data, (list, tuple)):
            data = [data]
        if len(data) > 10:
            raise forms.ValidationError('Envie no máximo 10 imagens por vez.')

        imagens = []
        for imagem in data:
            imagem = super().clean(imagem, initial)
            if imagem.size > MAX_IMAGE_SIZE:
                raise forms.ValidationError(
                    f'A imagem "{imagem.name}" deve ter no máximo 5 MB.'
                )
            try:
                with Image.open(imagem) as imagem_aberta:
                    imagem_aberta.verify()
            except (Image.Error, OSError) as error:
                raise forms.ValidationError(
                    f'O arquivo "{imagem.name}" não é uma imagem válida.'
                ) from error
            imagem.seek(0)
            imagens.append(imagem)
        return imagens


class AcaoImagemForm(forms.Form):
    imagens = MultipleImageField(
        label='Imagens',
        widget=MultipleFileInput(attrs={
            'accept': 'image/jpeg,image/png,image/webp',
        }),
    )
    descricao = forms.CharField(
        label='Descrição',
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Descrição opcional das imagens',
        }),
    )



class AcaoParticipanteForm(forms.ModelForm):
    class Meta:
        model = AcaoParticipante
        fields = ['voluntario', 'observacao']
        widgets = {
            'voluntario': forms.Select(attrs={'class': 'form-control'}),
            'observacao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Adicione uma observação sobre a participação',
            }),
        }

    def __init__(self, *args, acao=None, **kwargs):
        super().__init__(*args, **kwargs)
        participantes = AcaoParticipante.objects.filter(acao=acao)
        historico = AcaoParticipanteHistorico.objects.filter(acao=acao)
        self.fields['voluntario'].queryset = Voluntario.objects.filter(
            status='ATIVO'
        ).exclude(
            id_voluntario__in=participantes.values('voluntario_id')
        ).exclude(
            id_voluntario__in=historico.values('voluntario_id')
        ).order_by('nome')
        self.fields['voluntario'].empty_label = 'Selecione um voluntário'
        self.fields['voluntario'].label_from_instance = (
            lambda voluntario: f'{voluntario.nome} - {voluntario.email}'
        )


class AcaoResponsavelForm(forms.ModelForm):
    class Meta:
        model = AcaoResponsavel
        fields = ['voluntario', 'papel']
        widgets = {
            'voluntario': forms.Select(attrs={'class': 'form-control'}),
            'papel': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, acao=None, **kwargs):
        super().__init__(*args, **kwargs)
        cadastrados = AcaoResponsavel.objects.filter(acao=acao)
        self.fields['voluntario'].queryset = Voluntario.objects.filter(
            status='ATIVO'
        ).exclude(
            id_voluntario__in=cadastrados.values('voluntario_id')
        ).order_by('nome')
        self.fields['voluntario'].empty_label = 'Selecione um voluntário'
        self.fields['voluntario'].label_from_instance = (
            lambda voluntario: f'{voluntario.nome} - {voluntario.email}'
        )
