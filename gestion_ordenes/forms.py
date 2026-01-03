from django import forms
from .models import BitacoraOrden, Cotizacion, Transferencia, ItemTransferido
from catalogo.models import TipoServicio

# --- Formularios base ---
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

# --- COTIZACIONES (CON LÓGICA DE ESTADOS) ---
class CotizacionForm(forms.ModelForm):
    class Meta:
        model = Cotizacion
        fields = [
            'concepto', 'tipo_cotizacion', 'proveedor', 
            'fuente_refaccion', 'costo_refacciones', 'costo_mano_obra', 
            'estado', 'notas'
        ]
        widgets = {
            'concepto': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Descripción detallada del trabajo...', 'required': True}),
            'tipo_cotizacion': forms.Select(attrs={'class': 'form-control'}),
            'notas': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Observaciones internas, condiciones o detalles adicionales...'}),
            
            'costo_refacciones': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'required': True}),
            'costo_mano_obra': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'required': True}),
            
            'estado': forms.Select(attrs={'class': 'form-control'}),
            'fuente_refaccion': forms.Select(attrs={'class': 'form-control', 'id': 'id_fuente_refaccion', 'required': True}),
            'proveedor': forms.Select(attrs={'class': 'form-control', 'id': 'id_proveedor'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # LÓGICA DE ESTADOS
        if not self.instance.pk:
            # MODO CREACIÓN:
            # Eliminamos el campo 'estado' para que el usuario no pueda elegirlo.
            # Al guardar, el modelo usará su valor por defecto: 'Pendiente'.
            if 'estado' in self.fields:
                del self.fields['estado']
        else:
            # MODO EDICIÓN:
            # Filtramos las opciones según el estado actual
            estado_actual = self.instance.estado
            opciones_validas = []

            # Mapa de transiciones permitidas
            # 1. Pendiente -> Puede pasar a Enviada (o quedarse igual)
            if estado_actual == Cotizacion.ESTADO_PENDIENTE:
                opciones_validas = [
                    (Cotizacion.ESTADO_PENDIENTE, 'Pendiente de Enviar'),
                    (Cotizacion.ESTADO_ENVIADA, 'Enviada al Cliente')
                ]
            
            # 2. Enviada -> Puede ser Autorizada o Rechazada (o corregir a Pendiente si hubo error, opcionalmente)
            # Aquí seguimos la regla estricta: Solo a Autorizada/Rechazada
            elif estado_actual == Cotizacion.ESTADO_ENVIADA:
                opciones_validas = [
                    (Cotizacion.ESTADO_ENVIADA, 'Enviada al Cliente'),
                    (Cotizacion.ESTADO_AUTORIZADA, 'Autorizada'),
                    (Cotizacion.ESTADO_RECHAZADA, 'Rechazada')
                ]
            
            # 3. Estados Finales (Autorizada/Rechazada) -> Normalmente no se mueven, 
            # pero permitimos ver su estado actual para que el campo no aparezca vacío o roto.
            else:
                # Obtenemos la etiqueta legible del modelo
                label = dict(Cotizacion.ESTADO_COTIZACION).get(estado_actual, estado_actual)
                opciones_validas = [(estado_actual, label)]

            self.fields['estado'].choices = opciones_validas

    def clean(self):
        cleaned_data = super().clean()
        fuente = cleaned_data.get('fuente_refaccion')
        proveedor = cleaned_data.get('proveedor')
        costo_ref = cleaned_data.get('costo_refacciones') or 0
        costo_mo = cleaned_data.get('costo_mano_obra') or 0

        # Validación de Proveedor
        if fuente == 'Pedido a proveedor' and not proveedor:
            self.add_error('proveedor', 'Debe seleccionar un proveedor si el origen es externo.')
        
        if fuente == 'Stock interno':
            cleaned_data['proveedor'] = None

        # Validación de Costos
        if costo_ref + costo_mo <= 0:
            msg = "El total de la cotización debe ser mayor a 0."
            self.add_error('costo_refacciones', msg)
            self.add_error('costo_mano_obra', msg)
        
        return cleaned_data

# --- TRANSFERENCIAS (MEJORADO) ---
class TransferenciaForm(forms.ModelForm):
    class Meta:
        model = Transferencia
        fields = ['documento_referencia', 'notas']
        widgets = {
            'documento_referencia': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Ticket #123, Solicitud #45'}),
            'notas': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Justificación o comentarios...'}),
        }

class ItemTransferidoForm(forms.ModelForm):
    class Meta:
        model = ItemTransferido
        # Agregamos 'modelo'
        fields = ['descripcion_item', 'modelo', 'cantidad', 'numero_serie']
        widgets = {
            'descripcion_item': forms.TextInput(attrs={'class': 'form-control', 'required': True, 'placeholder': 'Ej. Memoria RAM DDR4 8GB'}),
            'modelo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Opcional'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'required': True}),
            'numero_serie': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'S/N si aplica'}),
        }