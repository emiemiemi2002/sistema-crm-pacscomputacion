from django.db import models
from django.conf import settings # Para referenciar al modelo User
# Importar modelos de otras apps
from gestion_clientes.models import Cliente, Equipo
from catalogo.models import Proveedor, TipoServicio

class OrdenServicio(models.Model):
    """La tabla central que representa una orden de servicio."""
    # Opciones para el campo 'estado'
    ESTADO_NUEVA = 'Nueva'
    ESTADO_DIAGNOSTICO = 'En diagnóstico'
    ESTADO_ESPERANDO_AUTORIZACION = 'Esperando autorización'
    ESTADO_ESPERANDO_REFACCION = 'Esperando refacción'
    ESTADO_EN_REPARACION = 'En reparación'
    ESTADO_FINALIZADA_TECNICO = 'Finalizada por Técnico'
    ESTADO_ENTREGADA = 'Entregada'
    ESTADO_CANCELADA = 'Cancelada'
    ESTADO_OPCIONES = [
        (ESTADO_NUEVA, 'Nueva'),
        (ESTADO_DIAGNOSTICO, 'En diagnóstico'),
        (ESTADO_ESPERANDO_AUTORIZACION, 'Esperando autorización'),
        (ESTADO_ESPERANDO_REFACCION, 'Esperando refacción'),
        (ESTADO_EN_REPARACION, 'En reparación'),
        (ESTADO_FINALIZADA_TECNICO, 'Finalizada por Técnico'),
        (ESTADO_ENTREGADA, 'Entregada'),
        (ESTADO_CANCELADA, 'Cancelada'),
    ]

    # Opciones para el campo 'prioridad'
    PRIORIDAD_BAJA = 'Baja'
    PRIORIDAD_NORMAL = 'Normal'
    PRIORIDAD_ALTA = 'Alta'
    PRIORIDAD_OPCIONES = [
        (PRIORIDAD_BAJA, 'Baja'),
        (PRIORIDAD_NORMAL, 'Normal'),
        (PRIORIDAD_ALTA, 'Alta'),
    ]

    # No es necesario id_orden, Django lo crea automáticamente como 'id' (AutoField PK) que funcionará como folio
    # on_delete=models.PROTECT: Evita borrar un cliente/equipo si tiene órdenes asociadas.
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="ordenes")
    equipo = models.ForeignKey(Equipo, on_delete=models.PROTECT, related_name="ordenes")

    # on_delete=models.SET_NULL: Si se elimina un usuario, la orden no se borra, solo se desvincula.
    # related_name permite acceder a las órdenes desde el usuario (ej. user.ordenes_recibidas.all())
    asistente_receptor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="ordenes_recibidas",
        verbose_name="Asistente que recibió"
    )
    tecnico_asignado = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True, # Puede no asignarse de inmediato
        related_name="ordenes_asignadas",
        verbose_name="Técnico asignado"
    )
    # ManyToManyField para asociar múltiples servicios a una orden
    servicios = models.ManyToManyField(
        TipoServicio,
        blank=True, # Puede que no se aplique un servicio del catálogo
        related_name="ordenes",
        verbose_name="Servicios aplicados"
    )

    descripcion_falla = models.TextField(verbose_name="Descripción de la falla")
    contrasena_equipo = models.CharField(max_length=255, blank=True, null=True, verbose_name="Contraseña del equipo (Encriptada)") # Recordar encriptar/desencriptar en las vistas <-------------------
    estado = models.CharField(max_length=50, choices=ESTADO_OPCIONES, default=ESTADO_NUEVA)
    prioridad = models.CharField(max_length=20, choices=PRIORIDAD_OPCIONES, default=PRIORIDAD_NORMAL)
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    fecha_cierre = models.DateTimeField(blank=True, null=True, verbose_name="Fecha de cierre")

    class Meta:
        verbose_name = "Orden de Servicio"
        verbose_name_plural = "Órdenes de Servicio"
        ordering = ['-fecha_creacion'] # Mostrar las más recientes primero por defecto

    def __str__(self):
        # Usamos el PK 'id' que Django crea automáticamente como folio
        return f"Orden #{self.id} - {self.cliente.nombre_completo}"

# --- Modelos relacionados con OrdenServicio ---

class Cotizacion(models.Model):
    """Almacena las cotizaciones asociadas a una orden de servicio."""
    # Opciones de Estado
    ESTADO_PENDIENTE = 'Pendiente'
    ESTADO_ENVIADA = 'Enviada'
    ESTADO_AUTORIZADA = 'Autorizada'
    ESTADO_RECHAZADA = 'Rechazada'
    ESTADO_COTIZACION = [
        (ESTADO_PENDIENTE, 'Pendiente de Enviar'),
        (ESTADO_ENVIADA, 'Enviada al Cliente'),
        (ESTADO_AUTORIZADA, 'Autorizada'),
        (ESTADO_RECHAZADA, 'Rechazada'),
    ]

    # Opciones Fuente Refacción
    FUENTE_STOCK = 'Stock interno'
    FUENTE_PROVEEDOR = 'Pedido a proveedor'
    FUENTE_REFACCION = [
        (FUENTE_STOCK, 'Stock interno'),
        (FUENTE_PROVEEDOR, 'Pedido a proveedor'),
    ]

    # Opciones Tipo Cotización
    TIPO_COTIZACION_INTERNA = 'Cotización interna'
    TIPO_COTIZACION_EXTERNA = 'Cotización externa'
    TIPO_COTIZACION = [
        (TIPO_COTIZACION_INTERNA, 'Cotización interna (Recepción)'),
        (TIPO_COTIZACION_EXTERNA, 'Cotización externa (Ventas)'),
    ]

    # No es necesario id_cotizacion, Django lo crea automáticamente como 'id' (AutoField PK)
    orden = models.ForeignKey(OrdenServicio, on_delete=models.CASCADE, related_name="cotizaciones")
    proveedor = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True, blank=True, related_name="cotizaciones")
    usuario_creador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="cotizaciones_creadas")

    concepto = models.TextField()
    costo_refacciones = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    costo_mano_obra = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    estado = models.CharField(max_length=50, choices=ESTADO_COTIZACION, default=ESTADO_PENDIENTE)
    fuente_refaccion = models.CharField(max_length=50, choices=FUENTE_REFACCION, blank=True, null=True, verbose_name="Fuente de la refacción")
    tipo_cotizacion = models.CharField(max_length=50, choices=TIPO_COTIZACION, default=TIPO_COTIZACION_INTERNA, verbose_name="Tipo de cotización")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación") # Añadido para mejor seguimiento
    notas = models.TextField(blank=True, null=True, verbose_name="Notas/Observaciones") # Añadido para mejor seguimiento

    class Meta:
        verbose_name = "Cotización"
        verbose_name_plural = "Cotizaciones"
        ordering = ['-fecha_creacion']

    @property
    def costo_total(self):
        return self.costo_refacciones + self.costo_mano_obra

    def __str__(self):
        return f"Cotización #{self.id} para Orden #{self.orden.id} ({self.get_estado_display()})"


class Transferencia(models.Model):
    """Modela el movimiento de piezas del almacén general a una orden de servicio."""
    # No es necesario id_transferencia, Django lo crea automáticamente como 'id' (AutoField PK)
    orden = models.ForeignKey(OrdenServicio, on_delete=models.CASCADE, related_name="transferencias")
    usuario_solicitante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="transferencias_solicitadas",
        verbose_name="Usuario solicitante"
    )
    usuario_autoriza = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="transferencias_autorizadas",
        verbose_name="Usuario que autoriza"
    )
    documento_referencia = models.CharField(max_length=100, blank=True, null=True, verbose_name="Documento de referencia")
    fecha_transferencia = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de transferencia")
    notas = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Transferencia de Almacén"
        verbose_name_plural = "Transferencias de Almacén"
        ordering = ['-fecha_transferencia']

    def __str__(self):
        return f"Transferencia #{self.id} para Orden #{self.orden.id}"


class ItemTransferido(models.Model):
    """Detalla cada uno de los artículos incluidos en una transferencia."""
    # No es necesario id_item, Django lo crea automáticamente como 'id' (AutoField PK)
    transferencia = models.ForeignKey(Transferencia, on_delete=models.CASCADE, related_name="items")
    descripcion_item = models.CharField(max_length=255, verbose_name="Descripción del ítem")
    modelo = models.CharField(max_length=100, blank=True, null=True)
    numero_serie = models.CharField(max_length=100, blank=True, null=True, verbose_name="Número de serie")
    cantidad = models.PositiveIntegerField(default=1) # Usar PositiveIntegerField para cantidades

    class Meta:
        verbose_name = "Ítem Transferido"
        verbose_name_plural = "Ítems Transferidos"

    def __str__(self):
        display = f"{self.cantidad} x {self.descripcion_item}"
        if self.numero_serie:
            display += f" (S/N: {self.numero_serie})"
        return display


class BitacoraOrden(models.Model):
    """Actúa como el historial de notas y eventos de una orden."""
    # No es necesario id_entrada, Django lo crea automáticamente como 'id' (AutoField PK)
    orden = models.ForeignKey(OrdenServicio, on_delete=models.CASCADE, related_name="bitacora")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="entradas_bitacora")
    fecha_hora = models.DateTimeField(auto_now_add=True, verbose_name="Fecha y Hora")
    descripcion = models.TextField()

    class Meta:
        verbose_name = "Entrada de Bitácora"
        verbose_name_plural = "Bitácora de Órdenes" # Ajustado para claridad
        ordering = ['-fecha_hora'] # Mostrar las entradas más recientes primero

    def __str__(self):
        username = self.usuario.username if self.usuario else "Sistema"
        return f"Entrada en Orden #{self.orden.id} - {self.fecha_hora.strftime('%Y-%m-%d %H:%M')}"
