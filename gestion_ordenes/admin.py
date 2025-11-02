from django.contrib import admin
from .models import OrdenServicio, Cotizacion, Transferencia, ItemTransferido, BitacoraOrden

# Register your models here.
admin.site.register(OrdenServicio)
admin.site.register(Cotizacion)
admin.site.register(Transferencia)
admin.site.register(ItemTransferido)
admin.site.register(BitacoraOrden)
