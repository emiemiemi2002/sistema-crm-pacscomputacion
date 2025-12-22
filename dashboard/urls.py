from django.urls import path
from . import views

urlpatterns = [
    # Ruta raíz del dashboard (el router)
    path('', views.dashboard_home, name='dashboard_home'),
    
    # Rutas específicas (por si alguien quiere entrar directo o para recargar)
    path('recepcion/', views.dashboard_recepcion, name='dashboard_recepcion'),
    path('tecnico/', views.dashboard_tecnico, name='dashboard_tecnico'),
    path('gerencia/', views.dashboard_gerente, name='dashboard_gerente'),
]