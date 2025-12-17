from django import forms
from django.forms import inlineformset_factory
from .models import BitacoraOrden, Cotizacion, Transferencia, ItemTransferido
from catalogo.models import TipoServicio

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

class AgregarServicioForm(forms.Form):
    servicio = forms.ModelChoiceField(
        queryset=TipoServicio.objects.all().order_by('nombre_servicio'),
        widget=forms.Select(attrs={'class': 'filter-control', 'style': 'width: 100%;'}),
        label="Seleccionar Servicio",
        empty_label="-- Selecciona un servicio del catálogo --"
    )

# --- Formulario de Cotización ---
class CotizacionForm(forms.ModelForm):
    class Meta:
        model = Cotizacion
        fields = ['concepto', 'proveedor', 'fuente_refaccion', 'costo_refacciones', 'costo_mano_obra', 'estado']
        widgets = {
            'concepto': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Describe qué incluye esta cotización...'}),
            'costo_refacciones': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'costo_mano_obra': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }
        labels = {
            'fuente_refaccion': 'Fuente de la Refacción',
            'costo_refacciones': 'Costo Refacciones ($)',
            'costo_mano_obra': 'Costo Mano de Obra ($)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Estilizar todos los campos
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})

# --- Formularios para Transferencias ---

class TransferenciaForm(forms.ModelForm):
    class Meta:
        model = Transferencia
        fields = ['documento_referencia', 'notas']
        widgets = {
            'notas': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Notas adicionales para almacén...'}),
            'documento_referencia': forms.TextInput(attrs={'placeholder': 'Folio físico, Ticket, etc. (Opcional)'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})

class ItemTransferidoForm(forms.ModelForm):
    class Meta:
        model = ItemTransferido
        fields = ['descripcion_item', 'cantidad', 'numero_serie']
        widgets = {
            'descripcion_item': forms.TextInput(attrs={'placeholder': 'Descripción de la pieza/refacción'}),
            'cantidad': forms.NumberInput(attrs={'min': '1', 'value': '1', 'style': 'width: 80px;'}),
            'numero_serie': forms.TextInput(attrs={'placeholder': 'S/N (Opcional)'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})

# Formset Factory: Permite gestionar múltiples items dentro del formulario de Transferencia
ItemTransferidoFormSet = inlineformset_factory(
    Transferencia, 
    ItemTransferido, 
    form=ItemTransferidoForm,
    extra=1,       # Mostrar 1 fila vacía por defecto
    can_delete=True # Permitir borrar filas
)