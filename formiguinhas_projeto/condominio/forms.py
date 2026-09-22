from django import forms
from django.utils import timezone

from .models import Bag, Condominio, MovimentacaoBag


class CondominioForm(forms.ModelForm):
    class Meta:
        model = Condominio
        fields = [
            'nome', 'responsavel_nome', 'responsavel_telefone', 'responsavel_email',
            'endereco', 'numero', 'complemento', 'bairro', 'cidade', 'estado', 'cep',
            'praia', 'porte', 'confiabilidade', 'status', 'observacoes',
        ]
        widgets = {
            'nome': forms.TextInput(attrs={
                'placeholder': 'Nome do condomínio',
            }),
            'responsavel_nome': forms.TextInput(attrs={
                'placeholder': 'Nome do responsável',
            }),
            'responsavel_telefone': forms.TextInput(attrs={
                'class': 'telefone-input',
                'inputmode': 'numeric',
                'maxlength': '15',
                'placeholder': '(11) 99999-9999',
            }),
            'responsavel_email': forms.EmailInput(attrs={
                'class': 'email-input',
                'inputmode': 'email',
                'placeholder': 'responsavel@email.com',
            }),
            'endereco': forms.TextInput(attrs={
                'autocomplete': 'address-line1',
                'placeholder': 'Rua, avenida ou logradouro',
            }),
            'numero': forms.TextInput(attrs={'placeholder': 'Número'}),
            'complemento': forms.TextInput(attrs={'placeholder': 'Bloco, apto. ou sala (opcional)'}),
            'bairro': forms.TextInput(attrs={
                'autocomplete': 'address-level3',
                'placeholder': 'Bairro',
            }),
            'cidade': forms.TextInput(attrs={
                'autocomplete': 'address-level2',
                'placeholder': 'Cidade',
            }),
            'estado': forms.TextInput(attrs={
                'class': 'estado-input',
                'autocomplete': 'address-level1',
                'maxlength': '2',
                'placeholder': 'UF',
            }),
            'cep': forms.TextInput(attrs={
                'class': 'cep-input',
                'inputmode': 'numeric',
                'maxlength': '9',
                'placeholder': '00000-000',
            }),
            'praia': forms.Select(attrs={
                'class': 'select-control',
            }),
            'porte': forms.Select(attrs={'class': 'select-control'}),
            'confiabilidade': forms.Select(attrs={'class': 'select-control'}),
            'status': forms.Select(attrs={'class': 'select-control'}),
            'observacoes': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Informações relevantes sobre o condomínio (opcional)',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            classes = field.widget.attrs.get('class', '')
            if 'form-control' not in classes.split():
                field.widget.attrs['class'] = f'{classes} form-control'.strip()
        self.fields['praia'].empty_label = 'Nenhuma praia vinculada'


class BagForm(forms.ModelForm):
    class Meta:
        model = Bag
        fields = ['codigo', 'condominio', 'status', 'peso_atual_kg', 'percentual_ocupacao', 'observacoes']
        labels = {
            'codigo': 'Código da bag',
            'condominio': 'Condomínio',
            'status': 'Status atual',
            'peso_atual_kg': 'Peso atual (kg)',
            'percentual_ocupacao': 'Ocupação (%)',
            'observacoes': 'Observações',
        }
        widgets = {
            'codigo': forms.TextInput(attrs={
                'placeholder': 'Ex.: BAG-0001',
                'autocomplete': 'off',
            }),
            'condominio': forms.Select(attrs={'class': 'select-control'}),
            'status': forms.Select(attrs={'class': 'select-control'}),
            'peso_atual_kg': forms.NumberInput(attrs={
                'inputmode': 'decimal',
                'min': '0',
                'step': '0.01',
                'placeholder': '0,00',
            }),
            'percentual_ocupacao': forms.NumberInput(attrs={
                'inputmode': 'numeric',
                'min': '0',
                'max': '100',
                'placeholder': '0 a 100',
            }),
            'observacoes': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Informações relevantes sobre a bag (opcional)',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            classes = field.widget.attrs.get('class', '')
            if 'form-control' not in classes.split():
                field.widget.attrs['class'] = f'{classes} form-control'.strip()
        self.fields['condominio'].empty_label = 'Selecione o condomínio'


class MovimentacaoBagForm(forms.ModelForm):
    class Meta:
        model = MovimentacaoBag
        fields = ['tipo', 'status_novo', 'data_movimentacao', 'observacao']
        labels = {
            'tipo': 'Tipo de movimentação',
            'status_novo': 'Novo status',
            'data_movimentacao': 'Data e hora',
            'observacao': 'Observação',
        }
        widgets = {
            'tipo': forms.Select(attrs={'class': 'select-control'}),
            'status_novo': forms.Select(attrs={'class': 'select-control'}),
            'data_movimentacao': forms.DateTimeInput(
                format='%d/%m/%Y %H:%M',
                attrs={
                    'type': 'text',
                    'class': 'data-hora-input',
                    'inputmode': 'numeric',
                    'maxlength': '16',
                    'placeholder': 'dd/mm/aaaa hh:mm',
                },
            ),
            'observacao': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Descreva o que aconteceu com a bag (opcional)',
            }),
        }

    def __init__(self, *args, bag=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.bag = bag
        self.fields['data_movimentacao'].input_formats = [
            '%d/%m/%Y %H:%M',
            '%Y-%m-%dT%H:%M',
        ]
        for field in self.fields.values():
            classes = field.widget.attrs.get('class', '')
            if 'form-control' not in classes.split():
                field.widget.attrs['class'] = f'{classes} form-control'.strip()
        if bag:
            self.initial['status_novo'] = bag.status
        if not self.is_bound and not self.initial.get('data_movimentacao'):
            self.initial['data_movimentacao'] = timezone.localtime().strftime(
                '%d/%m/%Y %H:%M'
            )
        self.fields['tipo'].choices = [
            ('', 'Selecione o tipo de movimentação'),
            *[
                choice for choice in self.fields['tipo'].choices
                if choice[0] != ''
            ],
        ]
        self.fields['status_novo'].choices = [
            ('', 'Selecione o novo status'),
            *[
                choice for choice in self.fields['status_novo'].choices
                if choice[0] != ''
            ],
        ]
