from django.db import models

class Cliente(models.Model):
    """Almacena la información completa de los clientes."""
    # No es necesario id_cliente, Django lo crea automáticamente como 'id' (AutoField PK)
    nombre_completo = models.CharField(max_length=255, verbose_name="Nombre Completo")
    telefono = models.CharField(max_length=20, unique=True)
    email = models.EmailField(max_length=254, unique=True, blank=True, null=True)
    rfc = models.CharField(max_length=13, blank=True, null=True, verbose_name="RFC")
    calle = models.CharField(max_length=255, blank=True, null=True)
    numero_exterior = models.CharField(max_length=20, blank=True, null=True, verbose_name="Número Exterior") # Ajustado max_length
    numero_interior = models.CharField(max_length=20, blank=True, null=True, verbose_name="Número Interior") # Ajustado max_length
    colonia = models.CharField(max_length=100, blank=True, null=True)
    codigo_postal = models.CharField(max_length=10, blank=True, null=True, verbose_name="Código Postal") # Ajustado max_length
    ciudad = models.CharField(max_length=100, blank=True, null=True)
    estado = models.CharField(max_length=100, blank=True, null=True)
    fecha_registro = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Registro")

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['nombre_completo']

    def __str__(self):
        return self.nombre_completo


class Equipo(models.Model):
    """Representa un equipo físico perteneciente a un cliente."""
    # No es necesario id_equipo, Django lo crea automáticamente como 'id' (AutoField PK)
    # on_delete=models.CASCADE: Si se borra un cliente, se borran sus equipos.
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="equipos")
    tipo_equipo = models.CharField(max_length=100, verbose_name="Tipo de Equipo", help_text="Ej. Laptop, Impresora, Proyector")
    marca = models.CharField(max_length=100)
    modelo = models.CharField(max_length=100)
    numero_serie = models.CharField(max_length=100, blank=True, null=True, verbose_name="Número de Serie")

    class Meta:
        verbose_name = "Equipo"
        verbose_name_plural = "Equipos"
        # Evitar números de serie duplicados para el mismo cliente (opcional pero recomendado)
        unique_together = [['cliente', 'numero_serie']]

    def __str__(self):
        display = f"{self.marca} {self.modelo}"
        if self.numero_serie:
            display += f" (S/N: {self.numero_serie})"
        return display
