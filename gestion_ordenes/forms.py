from django import forms
from .models import BitacoraOrden

class BitacoraForm(forms.ModelForm):
    class Meta:
        model = BitacoraOrden
        fields = ['descripcion']
        widgets = {
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3, 
                'placeholder': 'Escribe una nueva nota o actualización sobre el servicio...'
            }),
        }
        labels = {
            'descripcion': 'Nueva entrada en bitácora',
        }