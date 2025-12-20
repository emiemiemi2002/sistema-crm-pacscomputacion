from django import forms
from .models import BitacoraOrden, Cotizacion, Transferencia, ItemTransferido
from catalogo.models import TipoServicio

# --- Formularios base (Bitácora y Servicio) ---
class BitacoraForm(forms.ModelForm):
    class Meta:
        model = BitacoraOrden
        fields = ['descripcion']
        widgets = {
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Escribe una nota...'}),
        }

class AgregarServicioForm(forms.Form):
    servicio = forms.ModelChoiceField(
        queryset=TipoServicio.objects.all().order_by('nombre_servicio'),
        widget=forms.Select(attrs={'class': 'filter-control', 'style': 'width: 100%;'}),
        label="Seleccionar Servicio",
        empty_label="-- Selecciona un servicio --"
    )

# --- COTIZACIONES ---
class CotizacionForm(forms.ModelForm):
    class Meta:
        model = Cotizacion
        fields = ['concepto', 'proveedor', 'fuente_refaccion', 'costo_refacciones', 'costo_mano_obra', 'estado']
        widgets = {
            'concepto': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Descripción detallada...', 'required': True}),
            'costo_refacciones': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'required': True}),
            'costo_mano_obra': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'required': True}),
            'estado': forms.Select(attrs={'class': 'form-control'}),
            
            # IDs explícitos para que el JS los encuentre sin fallas
            'fuente_refaccion': forms.Select(attrs={'class': 'form-control', 'id': 'id_fuente_refaccion', 'required': True}),
            'proveedor': forms.Select(attrs={'class': 'form-control', 'id': 'id_proveedor'}),
        }
        labels = {
            'fuente_refaccion': 'Origen de Refacción *',
            'costo_refacciones': 'Costo Refacciones *',
            'costo_mano_obra': 'Costo Mano de Obra *',
            'proveedor': 'Proveedor',
        }

    def clean(self):
        cleaned_data = super().clean()
        fuente = cleaned_data.get('fuente_refaccion')
        proveedor = cleaned_data.get('proveedor')
        costo_ref = cleaned_data.get('costo_refacciones')
        costo_mo = cleaned_data.get('costo_mano_obra')

        # Validación estricta de campos numéricos (por si el HTML se salta)
        if costo_ref is None: self.add_error('costo_refacciones', 'Este campo es obligatorio.')
        if costo_mo is None: self.add_error('costo_mano_obra', 'Este campo es obligatorio.')

        # Lógica de Proveedor
        if fuente == 'Pedido a Proveedor' and not proveedor:
            self.add_error('proveedor', 'Si el origen es externo, debe seleccionar un proveedor.')
        
        if fuente == 'Stock Interno':
            cleaned_data['proveedor'] = None # Limpiar si seleccionó uno por error
        
        return cleaned_data

# --- TRANSFERENCIAS ---
class TransferenciaForm(forms.ModelForm):
    class Meta:
        model = Transferencia
        fields = ['documento_referencia', 'notas']
        widgets = {
            'documento_referencia': forms.TextInput(attrs={'class': 'form-control'}),
            'notas': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

class ItemTransferidoForm(forms.ModelForm):
    class Meta:
        model = ItemTransferido
        fields = ['descripcion_item', 'cantidad', 'numero_serie']
        widgets = {
            'descripcion_item': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'required': True, 'style': 'width: 80px;'}),
            'numero_serie': forms.TextInput(attrs={'class': 'form-control'}),
        }