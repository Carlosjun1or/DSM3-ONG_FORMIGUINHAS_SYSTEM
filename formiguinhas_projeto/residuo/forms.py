from django import forms

from .models import (
    ColetaResiduo,
    CATEGORIA_RESIDUO_CHOICES,
    DestinacaoResiduo,
    ItemColetaResiduo,
    ResiduoColetado,
    TIPO_RESIDUO_CHOICES,
    UNIDADE_RESIDUO_CHOICES,
)

RESIDUO_FIELDS = ['tipo', 'categoria', 'quantidade', 'unidade', 'observacao']
RESIDUO_LABELS = {
    'tipo': 'Tipo de resíduo',
    'categoria': 'Categoria',
    'quantidade': 'Quantidade ou peso',
    'unidade': 'Unidade de medida',
    'observacao': 'Observação',
}
RESIDUO_HELP_TEXTS = {
    'tipo': 'Selecione o material predominante, se já souber.',
    'categoria': 'Organiza o resíduo para consultas e relatórios.',
    'quantidade': 'Você pode preencher este dado depois.',
    'unidade': 'Escolha kg, litro ou unidade quando informar uma quantidade.',
}
RESIDUO_WIDGETS = {
    'tipo': forms.Select(attrs={'class': 'form-control'}),
    'categoria': forms.Select(attrs={'class': 'form-control'}),
    'quantidade': forms.NumberInput(attrs={
        'class': 'form-control',
        'step': '0.01',
        'min': '0',
        'inputmode': 'decimal',
        'placeholder': 'Ex.: 12,50',
    }),
    'unidade': forms.Select(attrs={'class': 'form-control'}),
    'observacao': forms.Textarea(attrs={
        'class': 'form-control',
        'rows': 3,
        'placeholder': 'Descreva o material ou outra informação (opcional)',
    }),
}


class DadosResiduoFormMixin:
    def __init__(self, *args, require_type_and_category=False, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = False
        if require_type_and_category:
            self.fields['tipo'].required = True
            self.fields['categoria'].required = True
        self.fields['tipo'].choices = [
            ('', 'Selecione o tipo de resíduo'),
            *TIPO_RESIDUO_CHOICES,
        ]
        self.fields['categoria'].choices = [
            ('', 'Selecione a categoria'),
            *CATEGORIA_RESIDUO_CHOICES,
        ]
        self.fields['unidade'].choices = [
            ('', 'Selecione a unidade'),
            *UNIDADE_RESIDUO_CHOICES,
        ]


class ColetaResiduoForm(forms.ModelForm):
    class Meta:
        model = ColetaResiduo
        fields = ['data_coleta', 'observacao']
        labels = {'data_coleta': 'Data e hora da coleta', 'observacao': 'Observação'}
        widgets = {
            'data_coleta': forms.DateTimeInput(
                format='%d/%m/%Y %H:%M',
                attrs={
                    'class': 'form-control',
                    'type': 'text',
                    'placeholder': 'dd/mm/aaaa hh:mm',
                },
            ),
            'observacao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descreva a coleta (opcional)',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['data_coleta'].input_formats = ['%d/%m/%Y %H:%M', '%Y-%m-%dT%H:%M']


class ItemColetaResiduoForm(DadosResiduoFormMixin, forms.ModelForm):
    class Meta:
        model = ItemColetaResiduo
        fields = RESIDUO_FIELDS
        labels = RESIDUO_LABELS
        help_texts = RESIDUO_HELP_TEXTS
        widgets = RESIDUO_WIDGETS


class ResiduoColetadoForm(DadosResiduoFormMixin, forms.ModelForm):
    class Meta:
        model = ResiduoColetado
        fields = RESIDUO_FIELDS
        labels = RESIDUO_LABELS
        help_texts = RESIDUO_HELP_TEXTS
        widgets = RESIDUO_WIDGETS


class DestinacaoResiduoForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = False
        self.fields['tipo'].choices = [
            ('', 'Selecione a destinação'),
            *DestinacaoResiduo.TIPO_CHOICES,
        ]
        self.fields['unidade'].choices = [
            ('', 'Selecione a unidade'),
            *DestinacaoResiduo.UNIDADE_CHOICES,
        ]

    class Meta:
        model = DestinacaoResiduo
        fields = ['tipo', 'quantidade', 'unidade', 'observacao']
        labels = {
            'tipo': 'Tipo de destinação',
            'quantidade': 'Quantidade destinada',
            'unidade': 'Unidade de medida',
            'observacao': 'Observação',
        }
        help_texts = {
            'tipo': 'Selecione o destino dado ao material, se já estiver definido.',
            'quantidade': 'Use para registrar apenas uma parte do resíduo, se necessário.',
            'unidade': 'Informe a unidade quando preencher a quantidade destinada.',
        }
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'quantidade': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.01', 'min': '0',
                'inputmode': 'decimal', 'placeholder': 'Ex.: 5,00',
            }),
            'unidade': forms.Select(attrs={'class': 'form-control'}),
            'observacao': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3,
                'placeholder': 'Informe detalhes do destino (opcional)',
            }),
        }

    def clean(self):
        return super().clean()
