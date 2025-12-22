import unicodedata
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.views.decorators.http import require_GET, require_POST
from django.core.paginator import Paginator
from django.utils.dateparse import parse_date
from django.utils import timezone
from django.db import transaction # Importante para guardar padre e hijos atómicamente
from django.forms import inlineformset_factory

from gestion_clientes.models import Cliente, Equipo
from catalogo.models import TipoServicio
from .models import OrdenServicio, BitacoraOrden, Cotizacion, Transferencia, ItemTransferido
from .forms import (
    BitacoraForm, AgregarServicioForm, CotizacionForm, 
    TransferenciaForm, ItemTransferidoForm
)

# --- UTILIDADES ---
def normalizar_texto(texto):
    if not texto:
        return ''
    return ''.join(c for c in unicodedata.normalize('NFD', str(texto).lower()) if unicodedata.category(c) != 'Mn')

# --- VISTAS GENERALES ---

@login_required
def lista_ordenes(request):
    ordenes = OrdenServicio.objects.all().select_related('cliente', 'tecnico_asignado', 'equipo').order_by('-fecha_creacion')
    filtro_estado = request.GET.get('estado')
    filtro_tecnico = request.GET.get('tecnico')
    filtro_prioridad = request.GET.get('prioridad')
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    
    if filtro_estado: ordenes = ordenes.filter(estado=filtro_estado)
    if filtro_tecnico: ordenes = ordenes.filter(tecnico_asignado__id=filtro_tecnico)
    if filtro_prioridad: ordenes = ordenes.filter(prioridad=filtro_prioridad)
    if fecha_inicio:
        d_inicio = parse_date(fecha_inicio)
        if d_inicio: ordenes = ordenes.filter(fecha_creacion__date__gte=d_inicio)
    if fecha_fin:
        d_fin = parse_date(fecha_fin)
        if d_fin: ordenes = ordenes.filter(fecha_creacion__date__lte=d_fin)

    paginator = Paginator(ordenes, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    tecnicos_list = User.objects.filter(groups__name='Técnico')
    
    context = {
        'page_obj': page_obj, 'tecnicos_list': tecnicos_list,
        'estados_opciones': OrdenServicio.ESTADO_OPCIONES, 'prioridades_opciones': OrdenServicio.PRIORIDAD_OPCIONES,
        'current_filters': {
            'estado': filtro_estado, 'tecnico': filtro_tecnico, 
            'prioridad': filtro_prioridad, 'fecha_inicio': fecha_inicio, 'fecha_fin': fecha_fin
        }
    }
    return render(request, 'gestion_ordenes/lista_ordenes.html', context)

@login_required
def crear_orden(request):
    if request.method == 'POST':
        cliente_id = request.POST.get('cliente_id')
        equipo_id = request.POST.get('equipo_id')
        descripcion = request.POST.get('descripcion_falla')
        contrasena = request.POST.get('contrasena_equipo')
        prioridad = request.POST.get('prioridad')
        tecnico_id = request.POST.get('tecnico_asignado')

        if cliente_id and equipo_id and descripcion:
            cliente = get_object_or_404(Cliente, pk=cliente_id)
            equipo = get_object_or_404(Equipo, pk=equipo_id)
            nueva_orden = OrdenServicio(
                cliente=cliente, equipo=equipo, descripcion_falla=descripcion, 
                contrasena_equipo=contrasena, prioridad=prioridad, 
                asistente_receptor=request.user, estado=OrdenServicio.ESTADO_NUEVA
            )
            if tecnico_id:
                nueva_orden.tecnico_asignado = User.objects.get(pk=tecnico_id)
            nueva_orden.save()
            messages.success(request, f'Orden #{nueva_orden.id} creada correctamente.')
            return redirect('lista_ordenes')

    tecnicos_list = User.objects.filter(groups__name='Técnico')
    context = {
        'tecnicos_list': tecnicos_list, 
        'prioridades': OrdenServicio.PRIORIDAD_OPCIONES,
        'cliente_pre': None, 'equipos_pre': []
    }
    return render(request, 'gestion_ordenes/crear_orden.html', context)

@login_required
@permission_required('gestion_ordenes.change_ordenservicio', raise_exception=True)
def editar_orden(request, orden_id):
    """Formulario de CIERRE para Recepción/Gerencia."""
    orden = get_object_or_404(OrdenServicio, pk=orden_id)

    if orden.fecha_cierre:
        messages.error(request, "Esta orden está cerrada y no permite cambios administrativos.")
        return redirect('detalle_orden', orden_id=orden.id)

    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado')
        if nuevo_estado in [OrdenServicio.ESTADO_ENTREGADA, OrdenServicio.ESTADO_CANCELADA]:
            # Validaciones de flujo
            if nuevo_estado == OrdenServicio.ESTADO_ENTREGADA and orden.estado != OrdenServicio.ESTADO_FINALIZADA_TECNICO:
                messages.error(request, "No se puede entregar si el técnico no ha finalizado.")
            else:
                with transaction.atomic():
                    orden.estado = nuevo_estado
                    orden.fecha_cierre = timezone.now()
                    orden.save()
                    BitacoraOrden.objects.create(
                        orden=orden, usuario=request.user,
                        descripcion=f"*** ORDEN CERRADA: {nuevo_estado} ***"
                    )
                messages.success(request, f"Orden #{orden.id} cerrada correctamente.")
                return redirect('lista_ordenes')

    estados_permitidos = []
    if orden.estado == OrdenServicio.ESTADO_FINALIZADA_TECNICO:
        estados_permitidos = [(OrdenServicio.ESTADO_ENTREGADA, 'Entregada')]
    else:
        estados_permitidos = [(OrdenServicio.ESTADO_CANCELADA, 'Cancelada')]

    return render(request, 'gestion_ordenes/editar_orden.html', {
        'orden': orden, 'estados_cierre': estados_permitidos
    })

@login_required
@permission_required('gestion_ordenes.delete_ordenservicio', raise_exception=True)
def eliminar_orden(request, orden_id):
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    if request.method == 'POST':
        folio = orden.id
        orden.delete()
        messages.success(request, f'Orden #{folio} eliminada correctamente.')
        return redirect('lista_ordenes')
    return render(request, 'gestion_ordenes/orden_confirm_delete.html', {'orden': orden})

@login_required
@require_GET
def buscar_cliente_api(request):
    query = request.GET.get('q', '').strip()
    if len(query) < 3: return JsonResponse({'resultados': []})
    query_norm = normalizar_texto(query)
    todos_clientes = Cliente.objects.all()
    resultados = []
    contador = 0
    for c in todos_clientes:
        if query_norm in normalizar_texto(c.nombre_completo) or query_norm in normalizar_texto(c.telefono):
            resultados.append({'id': c.id, 'nombre': c.nombre_completo, 'telefono': c.telefono, 'equipos': list(c.equipos.values('id', 'tipo_equipo', 'marca', 'modelo', 'numero_serie'))})
            contador += 1
        if contador >= 5: break
    return JsonResponse({'resultados': resultados})

# --- VISTAS DE DETALLE Y OPERACIONES ---

@login_required
def detalle_orden(request, orden_id):
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    cotizaciones = orden.cotizaciones.all().order_by('-id')
    bitacora = orden.bitacora.all().order_by('-fecha_hora')
    transferencias = orden.transferencias.all().select_related('usuario_solicitante', 'usuario_autoriza')
    
    if request.method == 'POST':
        if orden.fecha_cierre:
            messages.error(request, "No se pueden añadir notas a un expediente cerrado.")
            return redirect('detalle_orden', orden_id=orden.id)
            
        form_bitacora = BitacoraForm(request.POST)
        if form_bitacora.is_valid():
            nueva = form_bitacora.save(commit=False)
            nueva.orden = orden
            nueva.usuario = request.user
            nueva.save()
            messages.success(request, 'Nota agregada.')
            return redirect('detalle_orden', orden_id=orden.pk)
    
    context = {
        'orden': orden, 'cotizaciones': cotizaciones, 'bitacora': bitacora,
        'transferencias': transferencias, 'form_bitacora': BitacoraForm(),
        'form_servicio': AgregarServicioForm(), 'es_cerrada': orden.fecha_cierre is not None
    }
    return render(request, 'gestion_ordenes/detalle_orden.html', context)

@login_required
@require_POST
def agregar_servicio_orden(request, orden_id):
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    if orden.fecha_cierre:
        messages.error(request, "Acceso denegado: Orden cerrada.")
        return redirect('detalle_orden', orden_id=orden_id)
    
    form = AgregarServicioForm(request.POST)
    if form.is_valid():
        servicio = form.cleaned_data['servicio']
        if servicio not in orden.servicios.all():
            orden.servicios.add(servicio)
            BitacoraOrden.objects.create(orden=orden, usuario=request.user, descripcion=f"Servicio vinculado: {servicio.nombre_servicio}")
    return redirect('detalle_orden', orden_id=orden_id)

@login_required
def eliminar_servicio_orden(request, orden_id, servicio_id):
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    if orden.fecha_cierre: return redirect('detalle_orden', orden_id=orden_id)
    servicio = get_object_or_404(TipoServicio, pk=servicio_id)
    orden.servicios.remove(servicio)
    BitacoraOrden.objects.create(orden=orden, usuario=request.user, descripcion=f"Servicio eliminado: {servicio.nombre_servicio}")
    return redirect('detalle_orden', orden_id=orden_id)

# --- GESTIÓN COTIZACIONES ---

@login_required
def crear_cotizacion(request, orden_id):
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    if orden.fecha_cierre: return redirect('detalle_orden', orden_id=orden.id)
    if request.method == 'POST':
        form = CotizacionForm(request.POST)
        if form.is_valid():
            cot = form.save(commit=False)
            cot.orden = orden
            cot.usuario_creador = request.user
            cot.save()
            BitacoraOrden.objects.create(orden=orden, usuario=request.user, descripcion=f"Cotización registrada.")
            return redirect('detalle_orden', orden_id=orden.id)
    return render(request, 'gestion_ordenes/cotizacion_form.html', {'form': CotizacionForm(), 'orden': orden})

@login_required
@permission_required('gestion_ordenes.change_cotizacion', raise_exception=True)
def editar_cotizacion(request, orden_id, cotizacion_id):
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    cotizacion = get_object_or_404(Cotizacion, pk=cotizacion_id, orden=orden)
    estado_anterior = cotizacion.estado

    if request.method == 'POST':
        form = CotizacionForm(request.POST, instance=cotizacion)
        if form.is_valid():
            cotizacion = form.save()
            if estado_anterior != cotizacion.estado:
                BitacoraOrden.objects.create(orden=orden, usuario=request.user, descripcion=f"Cotización #{cotizacion.id} estado: {estado_anterior} -> {cotizacion.estado}")
            else:
                BitacoraOrden.objects.create(orden=orden, usuario=request.user, descripcion=f"Se actualizó la Cotización #{cotizacion.id}")
            
            messages.success(request, 'Cotización actualizada.')
            return redirect('detalle_orden', orden_id=orden.id)
    else:
        form = CotizacionForm(instance=cotizacion)

    return render(request, 'gestion_ordenes/cotizacion_form.html', {'form': form, 'orden': orden, 'editar': True})

@login_required
@permission_required('gestion_ordenes.delete_cotizacion', raise_exception=True)
def eliminar_cotizacion(request, orden_id, cotizacion_id):
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    cotizacion = get_object_or_404(Cotizacion, pk=cotizacion_id, orden=orden)
    
    # Bitácora antes de borrar
    BitacoraOrden.objects.create(
        orden=orden,
        usuario=request.user,
        descripcion=f"Se eliminó la Cotización #{cotizacion.id}"
    )
    
    cotizacion.delete()
    messages.success(request, 'Cotización eliminada.')
    return redirect('detalle_orden', orden_id=orden.id)

# --- GESTIÓN TRANSFERENCIAS ---

@login_required
def crear_transferencia(request, orden_id):
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    if orden.fecha_cierre: return redirect('detalle_orden', orden_id=orden.id)
    ItemFormSet = inlineformset_factory(Transferencia, ItemTransferido, form=ItemTransferidoForm, extra=1)
    if request.method == 'POST':
        form = TransferenciaForm(request.POST)
        formset = ItemFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                trans = form.save(commit=False)
                trans.orden = orden
                trans.usuario_solicitante = request.user
                trans.save()
                formset.instance = trans
                formset.save()
            return redirect('detalle_orden', orden_id=orden.id)
    return render(request, 'gestion_ordenes/transferencia_form.html', {
        'form': TransferenciaForm(), 'formset': ItemFormSet(queryset=ItemTransferido.objects.none()), 'orden': orden
    })

@login_required
@permission_required('gestion_ordenes.change_transferencia', raise_exception=True)
def editar_transferencia(request, orden_id, transferencia_id):
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    transferencia = get_object_or_404(Transferencia, pk=transferencia_id, orden=orden)
    
    # Bloqueo si ya está autorizado (regla de negocio)
    if transferencia.usuario_autoriza and not request.user.groups.filter(name='Gerente Servicio').exists():
        messages.error(request, 'Transferencia ya autorizada. Solo lectura.')
        return redirect('detalle_orden', orden_id=orden.id)

    # SOLUCIÓN: Fábrica con extra=0 para editar (NO agrega filas vacías automáticas)
    ItemFormSetEdit = inlineformset_factory(Transferencia, ItemTransferido, form=ItemTransferidoForm, extra=0, can_delete=True)

    if request.method == 'POST':
        form = TransferenciaForm(request.POST, instance=transferencia)
        formset = ItemFormSetEdit(request.POST, instance=transferencia)
        
        if form.is_valid() and formset.is_valid():
            items_validos = [f for f in formset if f.cleaned_data and not f.cleaned_data.get('DELETE', False)]
            
            if not items_validos:
                messages.error(request, 'La transferencia no puede quedar vacía.')
            else:
                form.save()
                formset.save()
                
                if 'btn_autorizar' in request.POST and request.user.has_perm('gestion_ordenes.change_transferencia'):
                    transferencia.usuario_autoriza = request.user
                    transferencia.save()
                    BitacoraOrden.objects.create(orden=orden, usuario=request.user, descripcion=f"AUTORIZADA Transferencia #{transferencia.id}")
                    messages.success(request, 'Transferencia autorizada.')
                else:
                    BitacoraOrden.objects.create(orden=orden, usuario=request.user, descripcion=f"Actualizada Transferencia #{transferencia.id}")
                    messages.success(request, 'Transferencia actualizada.')

                return redirect('detalle_orden', orden_id=orden.id)
    else:
        form = TransferenciaForm(instance=transferencia)
        formset = ItemFormSetEdit(instance=transferencia)

    return render(request, 'gestion_ordenes/transferencia_form.html', {
        'form': form, 'formset': formset, 'orden': orden, 'transferencia': transferencia, 'editar': True
    })

@login_required
@permission_required('gestion_ordenes.delete_transferencia', raise_exception=True)
def eliminar_transferencia(request, orden_id, transferencia_id):
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    transferencia = get_object_or_404(Transferencia, pk=transferencia_id, orden=orden)
    
    BitacoraOrden.objects.create(
        orden=orden,
        usuario=request.user,
        descripcion=f"Se eliminó/canceló la Transferencia #{transferencia.id}"
    )
    
    transferencia.delete()
    messages.success(request, 'Transferencia eliminada.')
    return redirect('detalle_orden', orden_id=orden.id)

@login_required
@permission_required('gestion_ordenes.change_ordenservicio', raise_exception=True)
@require_POST
def actualizar_estado_orden(request, orden_id):
    """Cambio de estado operativo (Técnico/Gerente)."""
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    if orden.fecha_cierre: return redirect('detalle_orden', orden_id=orden.id)
    
    nuevo_estado = request.POST.get('nuevo_estado')
    if nuevo_estado in dict(OrdenServicio.ESTADO_OPCIONES):
        anterior = orden.estado
        orden.estado = nuevo_estado
        orden.save()
        BitacoraOrden.objects.create(orden=orden, usuario=request.user, descripcion=f"Estado: {anterior} -> {nuevo_estado}")
        messages.success(request, f"Avance registrado: {nuevo_estado}")
    return redirect('detalle_orden', orden_id=orden.id)