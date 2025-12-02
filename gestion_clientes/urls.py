from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_clientes, name='lista_clientes'),
    
    # Es recomendable poner rutas específicas ANTES de las que usan IDs (<int:id>)
    path('crear/', views.crear_cliente, name='crear_cliente'), 
    path('equipos/crear/', views.crear_equipo, name='crear_equipo'),
    
    # Rutas con parámetros variables
    path('<int:id>/', views.detalle_cliente, name='detalle_cliente'),
    path('editar/<int:id>/', views.editar_cliente, name='editar_cliente'),
]