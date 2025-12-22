from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta

# Importamos modelos necesarios de otras apps
from gestion_ordenes.models import OrdenServicio, BitacoraOrden

@login_required
def dashboard_home(request):
    """
    Vista maestra (Router) que redirige al dashboard específico según el grupo del usuario.
    """
    user = request.user
    
    # Prioridad 1: Gerente o Superusuario (Acceso total)
    if user.groups.filter(name='Gerente Servicio').exists() or user.is_superuser:
        return redirect('dashboard_gerente')
    
    # Prioridad 2: Técnico (Vista operativa personal)
    elif user.groups.filter(name='Técnico').exists():
        return redirect('dashboard_tecnico')
    
    # Prioridad 3: Recepción (Vista operativa general)
    elif user.groups.filter(name='Asistente Recepción').exists():
        return redirect('dashboard_recepcion')
    
    # Fallback: Si no tiene grupo, lo mandamos a recepción o a una página genérica
    else:
        return redirect('dashboard_recepcion')

@login_required
def dashboard_recepcion(request):
    """
    UI-DASH-01: Centro de comando para recepción.
    """
    # 1. Definir el rango exacto de "HOY" en hora local
    # Esto evita problemas de desfase UTC en la base de datos
    now_local = timezone.localtime()
    inicio_dia = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    fin_dia = now_local.replace(hour=23, minute=59, second=59, microsecond=999999)

    # 2. KPI: Total Órdenes Activas
    total_abiertas = OrdenServicio.objects.exclude(
        estado__in=[
            OrdenServicio.ESTADO_ENTREGADA, 
            OrdenServicio.ESTADO_CANCELADA
        ]
    ).count()
    
    # 3. KPI: Cerradas Hoy (SOLUCIÓN IMPLEMENTADA)
    # Usamos __range con las horas exactas. Django convierte esto a UTC automáticamente al consultar.
    cerradas_hoy = OrdenServicio.objects.filter(
        fecha_cierre__range=(inicio_dia, fin_dia)
    ).count()

    # 4. Acciones Requeridas: Listas para Entregar
    ordenes_para_entrega = OrdenServicio.objects.filter(
        estado=OrdenServicio.ESTADO_FINALIZADA_TECNICO
    ).select_related('cliente', 'equipo').order_by('-fecha_creacion')[:5]
    
    # 5. Acciones Requeridas: Nuevas sin Asignar
    ordenes_sin_asignar = OrdenServicio.objects.filter(
        estado=OrdenServicio.ESTADO_NUEVA, 
        tecnico_asignado__isnull=True
    ).select_related('cliente', 'equipo').order_by('-fecha_creacion')[:5]

    # 6. Feed de Actividad Reciente
    ultimas_bitacoras = BitacoraOrden.objects.select_related('orden', 'usuario').order_by('-fecha_hora')[:8]

    context = {
        'kpi_abiertas': total_abiertas,
        'kpi_cerradas_hoy': cerradas_hoy,
        'ordenes_para_entrega': ordenes_para_entrega,
        'ordenes_sin_asignar': ordenes_sin_asignar,
        'feed_actividad': ultimas_bitacoras,
    }
    return render(request, 'dashboard/dash_recepcion.html', context)

@login_required
def dashboard_tecnico(request):
    """
    UI-DASH-02: Cola de trabajo personal del técnico.
    Enfoque: Lista limpia de tareas asignadas activas.
    """
    # Filtramos órdenes asignadas al usuario actual que NO estén cerradas
    mis_ordenes = OrdenServicio.objects.filter(
        tecnico_asignado=request.user
    ).exclude(
        estado__in=[
            OrdenServicio.ESTADO_ENTREGADA, 
            OrdenServicio.ESTADO_CANCELADA, 
            OrdenServicio.ESTADO_FINALIZADA_TECNICO # Si ya la terminó, sale de su cola
        ]
    ).select_related('cliente', 'equipo').order_by(
        # Orden personalizado: Prioridad Alta primero, luego por fecha (más antiguas primero)
        'prioridad', 'fecha_creacion'
    )
    
    # Conteo rápido de mis pendientes
    total_pendientes = mis_ordenes.count()

    context = {
        'mis_ordenes': mis_ordenes,
        'total_pendientes': total_pendientes,
    }
    return render(request, 'dashboard/dash_tecnico.html', context)

@login_required
def dashboard_gerente(request):
    """
    UI-DASH-03: Visión estratégica global.
    Enfoque: Gráficos y supervisión de alto nivel.
    """
    # 1. KPIs Globales
    total_ordenes_historico = OrdenServicio.objects.count()
    ordenes_activas = OrdenServicio.objects.exclude(
        estado__in=[OrdenServicio.ESTADO_ENTREGADA, OrdenServicio.ESTADO_CANCELADA]
    ).count()
    
    # 2. Datos para Gráficos (Agregación)
    
    # Gráfico 1: Distribución por Estado (Solo órdenes activas para que sea relevante)
    # Retorna: <QuerySet [{'estado': 'En reparación', 'total': 5}, ...]>
    ordenes_por_estado = OrdenServicio.objects.exclude(
        estado__in=[OrdenServicio.ESTADO_ENTREGADA, OrdenServicio.ESTADO_CANCELADA]
    ).values('estado').annotate(total=Count('estado')).order_by('-total')

    # Gráfico 2: Carga de Trabajo por Técnico (Cuántas tienen asignadas actualmente)
    carga_tecnicos = OrdenServicio.objects.exclude(
        estado__in=[OrdenServicio.ESTADO_ENTREGADA, OrdenServicio.ESTADO_CANCELADA, OrdenServicio.ESTADO_FINALIZADA_TECNICO]
    ).values(
        'tecnico_asignado__first_name', 'tecnico_asignado__username' # Usamos nombre real o username
    ).annotate(
        total=Count('id')
    ).order_by('-total')

    # 3. Alertas de Supervisión
    # Ejemplo: Órdenes de prioridad 'Alta' con más de 3 días de antigüedad que siguen abiertas
    fecha_limite = timezone.now() - timedelta(days=3)
    alertas_retraso = OrdenServicio.objects.filter(
        prioridad=OrdenServicio.PRIORIDAD_ALTA,
        fecha_creacion__lte=fecha_limite
    ).exclude(
        estado__in=[OrdenServicio.ESTADO_ENTREGADA, OrdenServicio.ESTADO_CANCELADA, OrdenServicio.ESTADO_FINALIZADA_TECNICO]
    ).select_related('tecnico_asignado')

    context = {
        'kpi_total': total_ordenes_historico,
        'kpi_activas': ordenes_activas,
        'data_estados': ordenes_por_estado,
        'data_tecnicos': carga_tecnicos,
        'alertas_retraso': alertas_retraso,
    }
    return render(request, 'dashboard/dash_gerente.html', context)