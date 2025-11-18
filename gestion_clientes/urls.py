from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_clientes, name='lista_clientes'),
    # Nueva ruta para el detalle. <int:id> captura el ID del cliente.
    path('<int:id>/', views.detalle_cliente, name='detalle_cliente'),
]