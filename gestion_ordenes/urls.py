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

    # Edición de orden
    path('editar/<int:orden_id>/', views.editar_orden, name='editar_orden'),
    path('eliminar/<int:orden_id>/', views.eliminar_orden, name='eliminar_orden'),

    # Rutas para Gestión de Servicios
    path('orden/<int:orden_id>/agregar-servicio/', views.agregar_servicio_orden, name='agregar_servicio_orden'),
    path('orden/<int:orden_id>/eliminar-servicio/<int:servicio_id>/', views.eliminar_servicio_orden, name='eliminar_servicio_orden'),

    # Gestión de Cotizaciones
    path('orden/<int:orden_id>/cotizacion/crear/', views.crear_cotizacion, name='crear_cotizacion'),
    path('orden/<int:orden_id>/cotizacion/editar/<int:cotizacion_id>/', views.editar_cotizacion, name='editar_cotizacion'),
    path('orden/<int:orden_id>/cotizacion/eliminar/<int:cotizacion_id>/', views.eliminar_cotizacion, name='eliminar_cotizacion'),

    # Gestión de Transferencias
    path('orden/<int:orden_id>/transferencia/crear/', views.crear_transferencia, name='crear_transferencia'),
    path('orden/<int:orden_id>/transferencia/editar/<int:transferencia_id>/', views.editar_transferencia, name='editar_transferencia'),
    path('orden/<int:orden_id>/transferencia/eliminar/<int:transferencia_id>/', views.eliminar_transferencia, name='eliminar_transferencia'),

    # Actualización de estado de la orden
    path('orden/<int:orden_id>/estado/', views.actualizar_estado_orden, name='actualizar_estado_orden'),
]