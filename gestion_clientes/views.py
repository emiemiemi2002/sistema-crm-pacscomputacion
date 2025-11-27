from django.shortcuts import render, redirect, get_object_or_404
#
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Cliente, Equipo
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

#
@login_required
def crear_equipo(request):
    """
    Vista para registrar un nuevo equipo.
    Puede recibir un 'cliente_id' en la URL para pre-seleccionar el cliente.
    """
    # Si venimos de la vista 'crear_orden', traeremos el ID del cliente
    cliente_preseleccionado_id = request.GET.get('cliente_id')
    cliente_obj = None
    if cliente_preseleccionado_id:
        cliente_obj = get_object_or_404(Cliente, pk=cliente_preseleccionado_id)

    if request.method == 'POST':
        # Procesar el formulario
        cliente_id = request.POST.get('cliente_id')
        tipo_equipo = request.POST.get('tipo_equipo')
        marca = request.POST.get('marca')
        modelo = request.POST.get('modelo')
        serie = request.POST.get('serie')

        if cliente_id and tipo_equipo and marca and modelo:
            cliente = get_object_or_404(Cliente, pk=cliente_id)
            
            nuevo_equipo = Equipo(
                cliente=cliente,
                tipo_equipo=tipo_equipo,
                marca=marca,
                modelo=modelo,
                numero_serie=serie
            )
            nuevo_equipo.save()
            
            messages.success(request, f'Equipo {marca} {modelo} registrado correctamente.')

            # Lógica de redirección inteligente
            next_url = request.GET.get('next')
            if next_url == 'crear_orden':
                # Si venía de crear orden, regresamos ahí con el cliente pre-seleccionado
                return redirect(f'/ordenes/crear/?cliente_id={cliente.id}')
            elif next_url == 'detalle_cliente':
                 return redirect('detalle_cliente', id=cliente.id)
            
            # Por defecto, ir al detalle del cliente dueño del equipo
            return redirect('detalle_cliente', id=cliente.id)

    # GET: Mostrar formulario
    # Si no hay cliente preseleccionado, necesitamos la lista completa para el select
    clientes_list = None
    if not cliente_obj:
        clientes_list = Cliente.objects.all().order_by('nombre_completo')

    # Obtenemos las opciones del modelo para el tipo de equipo
    tipos_equipo = Equipo.TIPO_EQUIPO_OPCIONES

    context = {
        'cliente_pre': cliente_obj,
        'clientes_list': clientes_list,
        'tipos_equipo': tipos_equipo,
    }
    return render(request, 'gestion_clientes/crear_equipo.html', context)
