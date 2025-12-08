from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.views.decorators.http import require_GET
from django.core.paginator import Paginator
from django.utils.dateparse import parse_date
from gestion_clientes.models import Cliente, Equipo
from .models import OrdenServicio
from .forms import BitacoraForm

#
@login_required
def lista_ordenes(request):
    """
    Vista para listar órdenes de servicio con filtros avanzados.
    """
    # 1. Obtener todos los registros base
    ordenes = OrdenServicio.objects.all().select_related('cliente', 'tecnico_asignado', 'equipo').order_by('-fecha_creacion')

    # 2. Capturar parámetros de filtro del GET
    filtro_estado = request.GET.get('estado')
    filtro_tecnico = request.GET.get('tecnico')
    filtro_prioridad = request.GET.get('prioridad')
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    query_search = request.GET.get('q') # Búsqueda general (opcional, si decides implementarla aquí también)

    # 3. Aplicar Filtros Dinámicamente
    if filtro_estado:
        ordenes = ordenes.filter(estado=filtro_estado)
    
    if filtro_tecnico:
        ordenes = ordenes.filter(tecnico_asignado__id=filtro_tecnico)
    
    if filtro_prioridad:
        ordenes = ordenes.filter(prioridad=filtro_prioridad)
    
    if fecha_inicio:
        date_start = parse_date(fecha_inicio)
        if date_start:
            ordenes = ordenes.filter(fecha_creacion__date__gte=date_start)
            
    if fecha_fin:
        date_end = parse_date(fecha_fin)
        if date_end:
            ordenes = ordenes.filter(fecha_creacion__date__lte=date_end)

    # 4. Paginación
    paginator = Paginator(ordenes, 10) # 10 órdenes por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # 5. Datos para los selectores del filtro
    # Obtenemos solo los usuarios que pertenecen al grupo 'Técnico' para el dropdown
    tecnicos_list = User.objects.filter(groups__name='Técnico')
    
    context = {
        'page_obj': page_obj,
        'tecnicos_list': tecnicos_list,
        # Pasamos las opciones del modelo para llenar los selects
        'estados_opciones': OrdenServicio.ESTADO_OPCIONES,
        'prioridades_opciones': OrdenServicio.PRIORIDAD_OPCIONES,
        # Pasamos los valores actuales para mantener el filtro seleccionado en la UI
        'current_filters': {
            'estado': filtro_estado,
            'tecnico': filtro_tecnico and int(filtro_tecnico), # Convertir a int para comparar en template
            'prioridad': filtro_prioridad,
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin
        }
    }

    return render(request, 'gestion_ordenes/lista_ordenes.html', context)

#
@login_required
def crear_orden(request):
    """
    Vista para el formulario de creación de una nueva orden de servicio.
    """
    if request.method == 'POST':
        # Procesar el formulario enviado
        cliente_id = request.POST.get('cliente_id')
        equipo_id = request.POST.get('equipo_id')
        descripcion = request.POST.get('descripcion_falla')
        contrasena = request.POST.get('contrasena_equipo')
        prioridad = request.POST.get('prioridad')
        tecnico_id = request.POST.get('tecnico_asignado')

        # Validaciones básicas (puedes usar Django Forms para esto, pero aquí lo hacemos manual para claridad)
        if cliente_id and equipo_id and descripcion:
            cliente = get_object_or_404(Cliente, pk=cliente_id)
            equipo = get_object_or_404(Equipo, pk=equipo_id)
            
            nueva_orden = OrdenServicio(
                cliente=cliente,
                equipo=equipo,
                descripcion_falla=descripcion,
                contrasena_equipo=contrasena,
                prioridad=prioridad,
                asistente_receptor=request.user, # El usuario logueado creó la orden
                estado=OrdenServicio.ESTADO_NUEVA # Estado inicial por defecto
            )

            if tecnico_id:
                tecnico = User.objects.get(pk=tecnico_id)
                nueva_orden.tecnico_asignado = tecnico

            nueva_orden.save()
            
            # Redirigir al detalle de la orden recién creada (asumiendo que ya tienes esa URL o la crearás pronto)
            # return redirect('detalle_orden', id=nueva_orden.id) 
            return redirect('lista_ordenes') # Por ahora redirigimos a la lista

    # GET: Mostrar el formulario vacío
    tecnicos_list = User.objects.filter(groups__name='Técnico')
    prioridades = OrdenServicio.PRIORIDAD_OPCIONES
    
    # Si venimos desde el detalle de cliente con un ID pre-seleccionado
    cliente_preseleccionado = None
    equipos_preseleccionados = []
    cliente_id_param = request.GET.get('cliente_id')
    
    if cliente_id_param:
        cliente_preseleccionado = get_object_or_404(Cliente, pk=cliente_id_param)
        equipos_preseleccionados = cliente_preseleccionado.equipos.all()

    context = {
        'tecnicos_list': tecnicos_list,
        'prioridades': prioridades,
        'cliente_pre': cliente_preseleccionado,
        'equipos_pre': equipos_preseleccionados,
    }
    return render(request, 'gestion_ordenes/crear_orden.html', context)

#
@login_required
@require_GET
def buscar_cliente_api(request):
    """
    API interna para buscar clientes y devolver sus datos y equipos en JSON.
    Se usa mediante AJAX desde el formulario de crear orden.
    """
    query = request.GET.get('q', '')
    if len(query) < 3:
        return JsonResponse({'resultados': []}) # No buscar si es muy corto

    clientes = Cliente.objects.filter(
        nombre_completo__icontains=query
    ) | Cliente.objects.filter(
        telefono__icontains=query
    )
    
    resultados = []
    for c in clientes[:5]: # Limitar a 5 resultados
        equipos = list(c.equipos.values('id', 'tipo_equipo', 'marca', 'modelo', 'numero_serie'))
        resultados.append({
            'id': c.id,
            'nombre': c.nombre_completo,
            'telefono': c.telefono,
            'equipos': equipos
        })
    
    return JsonResponse({'resultados': resultados})

#
@login_required
def detalle_orden(request, orden_id):
    # 1. Obtener la orden
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    
    # 2. Consultas de datos relacionados
    cotizaciones = orden.cotizaciones.all().order_by('-id')
    bitacora = orden.bitacora.all().order_by('-fecha_hora')
    
    # ACTUALIZADO: Consulta basada en tu modelo real de Transferencia
    # El modelo ya tiene 'ordering' en Meta, pero forzamos el orden por fecha para asegurar consistencia visual
    transferencias = orden.transferencias.all().select_related('usuario_solicitante', 'usuario_autoriza')

    # 3. Lógica para procesar el formulario de Bitácora
    if request.method == 'POST':
        form_bitacora = BitacoraForm(request.POST)
        if form_bitacora.is_valid():
            nueva_entrada = form_bitacora.save(commit=False)
            nueva_entrada.orden = orden
            nueva_entrada.usuario = request.user
            nueva_entrada.save()
            messages.success(request, 'Nota agregada a la bitácora.')
            return redirect('detalle_orden', orden_id=orden.pk)
    else:
        form_bitacora = BitacoraForm()

    context = {
        'orden': orden,
        'cotizaciones': cotizaciones,
        'transferencias': transferencias,
        'bitacora': bitacora,
        'form_bitacora': form_bitacora,
    }

    return render(request, 'gestion_ordenes/detalle_orden.html', context)