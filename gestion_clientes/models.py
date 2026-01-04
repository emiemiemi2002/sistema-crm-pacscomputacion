import base64
from django.db import models
from django.conf import settings
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# --- UTILERÍA DE ENCRIPTACIÓN ---
def obtener_fernet():
    """
    Genera una instancia de Fernet usando la SECRET_KEY de Django.
    Esto asegura que la clave sea única para tu proyecto y persistente.
    """
    # Usamos la llave secreta del proyecto como base
    key = settings.SECRET_KEY.encode()
    # Salt fijo para que la clave derivada sea siempre la misma para esta instancia
    salt = b'django_crm_pacs_salt' 
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key_b64 = base64.urlsafe_b64encode(kdf.derive(key))
    return Fernet(key_b64)

class Cliente(models.Model):
    """Almacena la información completa de los clientes."""
    # No es necesario id_cliente, Django lo crea automáticamente como 'id' (AutoField PK)
    nombre_completo = models.CharField(max_length=255, verbose_name="Nombre completo")
    telefono = models.CharField(max_length=20, unique=True, verbose_name="Teléfono")
    email = models.EmailField(max_length=254, blank=True, null=True, unique=True, verbose_name="Correo electrónico")
    rfc = models.CharField(max_length=13, blank=True, null=True, verbose_name="RFC")
    
    # Dirección
    calle = models.CharField(max_length=255, blank=True, null=True)
    numero_exterior = models.CharField(max_length=20, blank=True, null=True, verbose_name="Número Exterior") 
    numero_interior = models.CharField(max_length=20, blank=True, null=True, verbose_name="Número Interior") 
    colonia = models.CharField(max_length=100, blank=True, null=True)
    codigo_postal = models.CharField(max_length=10, blank=True, null=True, verbose_name="Código Postal")
    ciudad = models.CharField(max_length=100, blank=True, null=True)
    estado = models.CharField(max_length=100, blank=True, null=True)
    
    fecha_registro = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de registro")

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['nombre_completo']

    def __str__(self):
        return self.nombre_completo

    def save(self, *args, **kwargs):
        # MEJORA DE INTEGRIDAD: Limpieza de campos opcionales
        self.email = self.email or None
        self.rfc = self.rfc or None
        
        # Limpieza de dirección
        self.calle = self.calle or None
        self.numero_exterior = self.numero_exterior or None
        self.numero_interior = self.numero_interior or None
        self.colonia = self.colonia or None
        self.codigo_postal = self.codigo_postal or None
        self.ciudad = self.ciudad or None
        self.estado = self.estado or None
        
        super().save(*args, **kwargs)


class Equipo(models.Model):
    """Representa un dispositivo perteneciente a un cliente."""

    # Opciones para el campo 'tipo_equipo'
    TIPO_EQUIPO_LAPTOP = 'Laptop'
    TIPO_EQUIPO_ESCRITORIO = 'Computadora de escritorio'
    TIPO_EQUIPO_IMPRESORA = 'Impresora'
    TIPO_EQUIPO_PROYECTOR = 'Proyector'
    TIPO_EQUIPO_COMPONENTE = 'Componente de computadora'
    TIPO_EQUIPO_OPCIONES = [
        (TIPO_EQUIPO_LAPTOP, 'Laptop'),
        (TIPO_EQUIPO_ESCRITORIO, 'Computadora de escritorio'),
        (TIPO_EQUIPO_IMPRESORA, 'Impresora'),
        (TIPO_EQUIPO_PROYECTOR, 'Proyector'),
        (TIPO_EQUIPO_COMPONENTE, 'Componente de computadora'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="equipos")
    tipo_equipo = models.CharField(max_length=100, verbose_name="Tipo de equipo", choices=TIPO_EQUIPO_OPCIONES, help_text="Ej. Laptop, Impresora, Proyector")
    marca = models.CharField(max_length=100)
    modelo = models.CharField(max_length=100)
    numero_serie = models.CharField(max_length=100, blank=True, null=True, verbose_name="Número de Serie")
    
    contrasena_equipo = models.CharField(max_length=255, blank=True, null=True, verbose_name="Contraseña (Encriptada)")
    
    class Meta:
        verbose_name = "Equipo"
        verbose_name_plural = "Equipos"
        # Evitar número de serie duplicados para el mismo cliente
        unique_together = [['cliente', 'numero_serie']]

    def __str__(self):
        display = f"{self.marca} {self.modelo}"
        if self.numero_serie:
            display += f" (S/N: {self.numero_serie})"
        return display

    def save(self, *args, **kwargs):
        # MEJORA DE INTEGRIDAD: Limpieza crítica para unique_together
        self.numero_serie = self.numero_serie or None
        self.contrasena_equipo = self.contrasena_equipo or None
        super().save(*args, **kwargs)

    # --- MÉTODOS DE ENCRIPTACIÓN ---

    def set_password(self, raw_password):
        """
        Encripta la contraseña plana y la guarda en contrasena_equipo.
        Usa esto en las vistas/forms antes de guardar.
        """
        if raw_password:
            f = obtener_fernet()
            # Encriptamos y convertimos bytes a string para guardar en CharField
            token = f.encrypt(raw_password.encode('utf-8'))
            self.contrasena_equipo = token.decode('utf-8')
        else:
            self.contrasena_equipo = None

    def get_password(self):
        """
        Desencripta y devuelve la contraseña original (texto plano).
        Usa esto en las plantillas o vistas de detalle.
        """
        if self.contrasena_equipo:
            try:
                f = obtener_fernet()
                # Convertimos string a bytes y desencriptamos
                token = self.contrasena_equipo.encode('utf-8')
                return f.decrypt(token).decode('utf-8')
            except Exception:
                # Si falla (ej. clave cambió), retornamos algo seguro o vacío
                return "Error desencriptando"
        return None