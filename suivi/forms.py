from django import forms
from .models import Lot, Processus, Message

class LotForm(forms.ModelForm):
    class Meta:
        model = Lot
        fields = ['ref', 'quantite', 'epn', 'cpn', 'planificateur', 'projet', 'type','week']
        widgets = {
            'ref': forms.TextInput(attrs={'size': '20'}),
            'quantite': forms.NumberInput(attrs={'size': '10', 'min': '1'})
        }
    
    def clean_quantite(self):
        quantite = self.cleaned_data.get('quantite')
        if quantite <= 0:
            raise forms.ValidationError("La quantité doit être supérieure à 0.")
        return quantite

class ProcessForm(forms.Form):
    lot = forms.ModelChoiceField(
        queryset=Lot.objects.all(),
        label="Lot",
        widget=forms.Select(attrs={'style': 'width: 200px;'})
    )
    processus = forms.ModelChoiceField(
        queryset=Processus.objects.all(),
        label="Processus",
        widget=forms.Select(attrs={'style': 'width: 200px;'})
    )

class UploadFileForm(forms.Form):
    file = forms.FileField(label='Choisir un fichier Excel')

class ReclamationForm(forms.Form):
    lot = forms.CharField(
        label="Lot",
        max_length=100,
        widget=forms.TextInput(attrs={'style': 'width: 100%;', 'placeholder': 'Entrer le numéro de lot'})
    )
    processus = forms.ModelChoiceField(
        queryset=Processus.objects.all(),
        label="Processus",
        empty_label="Choisissez le processus",
        widget=forms.Select(attrs={'style': 'width: 100%;'})
    )
    le_message = forms.CharField(
        label="Message",
        widget=forms.Textarea(attrs={'style': 'width: 100%; height: 100px;'})
    )
    
    RESPONSABLE_CHOICES = [
        ('ingenierie', 'Ingénierie'),
        ('logistique', 'Logistique'),
        ('production', 'Production'),
        ('qualite', 'Qualité'),
    ]
    
    responsable = forms.ChoiceField(
        label="Département",
        choices=RESPONSABLE_CHOICES,
        widget=forms.Select(attrs={'style': 'width: 100%;'})
    )
