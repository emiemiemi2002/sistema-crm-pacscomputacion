from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.utils.dateparse import parse_date
from .models import OrdenServicio

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