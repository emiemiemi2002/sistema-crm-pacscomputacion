from django.urls import path
from . import views

urlpatterns = [
    # UI-OM-01: Lista general de órdenes
    path('', views.lista_ordenes, name='lista_ordenes'),

    # UI-OM-03: Formulario de creación de orden
    path('crear/', views.crear_orden, name='crear_orden'),

    # API Endpoint: Búsqueda de clientes vía AJAX (usado en crear_orden)
    path('api/buscar-cliente/', views.buscar_cliente_api, name='buscar_cliente_api'),

    # UI-OM-02: Detalle de orden
    path('orden/<int:orden_id>/', views.detalle_orden, name='detalle_orden'),
]