from django.urls import path
from . import views

urlpatterns = [
    # Vista Principal (Listas)
    path('', views.CatalogoListView.as_view(), name='lista_catalogos'),

    # Rutas para Proveedores
    path('proveedores/crear/', views.ProveedorCreateView.as_view(), name='crear_proveedor'),
    path('proveedores/editar/<int:pk>/', views.ProveedorUpdateView.as_view(), name='editar_proveedor'),
    path('proveedores/eliminar/<int:pk>/', views.ProveedorDeleteView.as_view(), name='eliminar_proveedor'),

    # Rutas para Tipos de Servicio
    path('servicios/crear/', views.TipoServicioCreateView.as_view(), name='crear_servicio'),
    path('servicios/editar/<int:pk>/', views.TipoServicioUpdateView.as_view(), name='editar_servicio'),
    path('servicios/eliminar/<int:pk>/', views.TipoServicioDeleteView.as_view(), name='eliminar_servicio'),
]