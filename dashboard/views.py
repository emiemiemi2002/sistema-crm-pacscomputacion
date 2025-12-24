import json
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Case, When, Value, IntegerField, Count, Q
from django.utils import timezone
from datetime import timedelta
from django.core.serializers.json import DjangoJSONEncoder # Para serializar fechas si fuera necesario

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
    UI-DASH-02: Dashboard Técnico corregido.
    """
    user = request.user
    
    # 1. CORRECCIÓN DE ORDENAMIENTO: Usar 'Normal' en lugar de 'Media'
    priority_order = Case(
        When(prioridad='Alta', then=Value(1)),
        When(prioridad='Normal', then=Value(2)), # Corregido
        When(prioridad='Baja', then=Value(3)),
        default=Value(4),
        output_field=IntegerField(),
    )

    # 2. Consulta Maestra
    mis_ordenes = OrdenServicio.objects.filter(
        tecnico_asignado=user
    ).exclude(
        estado__in=[
            OrdenServicio.ESTADO_FINALIZADA_TECNICO,
            OrdenServicio.ESTADO_ENTREGADA,
            OrdenServicio.ESTADO_CANCELADA
        ]
    ).select_related('cliente', 'equipo').annotate(
        prio_weight=priority_order
    ).order_by('prio_weight', 'fecha_creacion')

    # 3. KPIs Corregidos
    detenidas_refaccion = mis_ordenes.filter(estado=OrdenServicio.ESTADO_ESPERANDO_REFACCION).count()
    
    # CORRECCIÓN KPI: Solo contar "Nuevas" como pendientes de tocar.
    # Si ya está "En diagnóstico", el técnico ya la tomó, así que sale de este contador.
    pendientes_inicio = mis_ordenes.filter(estado=OrdenServicio.ESTADO_NUEVA).count()

    criticas = mis_ordenes.filter(prioridad='Alta').count()

    context = {
        'mis_ordenes': mis_ordenes,
        'stats': {
            'total': mis_ordenes.count(),
            'detenidas': detenidas_refaccion,
            'por_diagnosticar': pendientes_inicio, # Variable renombrada lógicamente, aunque en template usaremos la misma key o adaptamos
            'criticas': criticas,
        },
        'saludo': timezone.localtime().strftime('%H')
    }
    
    return render(request, 'dashboard/dash_tecnico.html', context)

@login_required
def dashboard_gerente(request):
    """
    UI-DASH-03: Dashboard Gerencial con datos serializados para Chart.js.
    """
    # 1. Consultas Base (Excluyendo cerradas para la carga actual)
    qs_activas = OrdenServicio.objects.exclude(
        estado__in=[OrdenServicio.ESTADO_ENTREGADA, OrdenServicio.ESTADO_CANCELADA]
    )

    # 2. KPIs
    total_historico = OrdenServicio.objects.count()
    total_activas = qs_activas.count()
    
    # Alertas: Alta prioridad + >3 días
    fecha_limite = timezone.now() - timedelta(days=3)
    alertas_qs = qs_activas.filter(
        prioridad=OrdenServicio.PRIORIDAD_ALTA,
        fecha_creacion__lte=fecha_limite
    ).select_related('cliente', 'tecnico_asignado')[:10] # Limitamos a 10 para no saturar
    
    total_sin_asignar = qs_activas.filter(tecnico_asignado__isnull=True).count()

    # 3. PROCESAMIENTO DE DATOS PARA GRÁFICOS (SERIALIZACIÓN JSON)
    
    # A) Gráfico de Estados
    raw_estados = qs_activas.values('estado').annotate(count=Count('id')).order_by('-count')
    
    estados_labels = [item['estado'] for item in raw_estados]
    estados_data = [item['count'] for item in raw_estados]

    # B) Gráfico de Carga de Técnicos
    # Excluimos los 'Sin asignar' para este gráfico
    raw_tecnicos = qs_activas.exclude(tecnico_asignado__isnull=True).values(
        'tecnico_asignado__first_name', 
        'tecnico_asignado__username'
    ).annotate(count=Count('id')).order_by('-count')
    
    tecnicos_labels = []
    for item in raw_tecnicos:
        nombre = item['tecnico_asignado__first_name']
        if not nombre:
            nombre = item['tecnico_asignado__username']
        tecnicos_labels.append(nombre)
        
    tecnicos_data = [item['count'] for item in raw_tecnicos]

    context = {
        'kpi_total': total_historico,
        'kpi_activas': total_activas,
        'kpi_retraso': alertas_qs.count(),
        'kpi_sin_asignar': total_sin_asignar,
        'alertas_retraso': alertas_qs,
        
        # DATOS JSON SEGUROS (Strings listos para JS)
        # Usamos json.dumps para asegurar comillas dobles y escape de caracteres
        'json_estados_labels': json.dumps(estados_labels, cls=DjangoJSONEncoder),
        'json_estados_data': json.dumps(estados_data, cls=DjangoJSONEncoder),
        'json_tecnicos_labels': json.dumps(tecnicos_labels, cls=DjangoJSONEncoder),
        'json_tecnicos_data': json.dumps(tecnicos_data, cls=DjangoJSONEncoder),
    }
    return render(request, 'dashboard/dash_gerente.html', context)