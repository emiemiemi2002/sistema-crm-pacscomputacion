from django.shortcuts import render, get_object_or_404
#
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from .models import Cliente
from gestion_ordenes.models import OrdenServicio

#
@login_required
def lista_clientes(request):
    """
    Vista para listar clientes con funcionalidad de búsqueda y paginación.
    """
    # Obtener el término de búsqueda de la URL (ej. ?q=Juan)
    query = request.GET.get('q')
    
    # Filtrar clientes si hay búsqueda, sino traer todos
    if query:
        clientes_list = Cliente.objects.filter(
            Q(nombre_completo__icontains=query) |
            Q(telefono__icontains=query) |
            Q(rfc__icontains=query) |
            Q(email__icontains=query)
        ).distinct()
    else:
        clientes_list = Cliente.objects.all()

    # Configurar paginación (10 clientes por página)
    paginator = Paginator(clientes_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'query': query, # Para mantener el texto en la caja de búsqueda
    }
    
    return render(request, 'gestion_clientes/lista_clientes.html', context)

#
@login_required
def detalle_cliente(request, id):
    """
    Muestra la información detallada de un cliente, sus equipos y su historial de órdenes.
    """
    # Obtiene el cliente o devuelve un error 404 si no existe
    cliente = get_object_or_404(Cliente, pk=id)
    
    # Obtener todas las órdenes asociadas a este cliente, ordenadas de la más reciente a la más antigua
    # Usamos 'ordenes' porque definimos related_name='ordenes' en el modelo OrdenServicio
    historial_ordenes = cliente.ordenes.all().order_by('-fecha_creacion')
    
    # Obtener los equipos registrados
    equipos = cliente.equipos.all()

    context = {
        'cliente': cliente,
        'historial_ordenes': historial_ordenes,
        'equipos': equipos,
    }
    
    return render(request, 'gestion_clientes/detalle_cliente.html', context)
