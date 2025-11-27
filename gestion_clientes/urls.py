from django.urls import path
from . import views

urlpatterns = [
    # UI-CLI-01: Lista de Clientes
    path('', views.lista_clientes, name='lista_clientes'),
    
    # UI-CLI-02: Detalle de Cliente
    path('<int:id>/', views.detalle_cliente, name='detalle_cliente'),
    
    # NUEVA RUTA: Crear Equipo (para el flujo optimizado)
    path('equipos/crear/', views.crear_equipo, name='crear_equipo'),
]