from django.db import models

class Proveedor(models.Model):
    """Almacena la información de los proveedores de refacciones."""
    # No es necesario id_proveedor, Django lo crea automáticamente como 'id' (AutoField PK)
    nombre_empresa = models.CharField(max_length=255, unique=True, verbose_name="Nombre de la empresa")
    persona_contacto = models.CharField(max_length=255, blank=True, null=True, verbose_name="Persona de contacto")
    telefono = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(max_length=254, blank=True, null=True)

    class Meta:
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"
        ordering = ['nombre_empresa'] # Ordenar alfabéticamente por defecto

    def __str__(self):
        return self.nombre_empresa


class TipoServicio(models.Model):
    """Catálogo de los servicios técnicos que ofrece la empresa."""
    # No es necesario id_servicio, Django lo crea automáticamente como 'id' (AutoField PK)
    nombre_servicio = models.CharField(max_length=255, unique=True, verbose_name="Nombre del servicio")
    descripcion = models.TextField(blank=True, null=True)
    costo_estandar = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Costo estándar")

    class Meta:
        verbose_name = "Tipo de Servicio"
        verbose_name_plural = "Tipos de Servicio"
        ordering = ['nombre_servicio']

    def __str__(self):
        return self.nombre_servicio
