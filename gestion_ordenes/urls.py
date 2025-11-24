from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_ordenes, name='lista_ordenes'),
    # Aquí añadiremos pronto: path('crear/', views.crear_orden, name='crear_orden'),
    # y path('<int:id>/', views.detalle_orden, name='detalle_orden'),
]