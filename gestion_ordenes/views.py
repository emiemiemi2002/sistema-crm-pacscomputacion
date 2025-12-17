import unicodedata
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.views.decorators.http import require_GET, require_POST
from django.core.paginator import Paginator
from django.utils.dateparse import parse_date
from django.db import transaction # Importante para guardar padre e hijos atómicamente
from gestion_clientes.models import Cliente, Equipo
from catalogo.models import TipoServicio
from .models import OrdenServicio, BitacoraOrden, Cotizacion, Transferencia
from .forms import (
    BitacoraForm, AgregarServicioForm, CotizacionForm, 
    TransferenciaForm, ItemTransferidoFormSet
)

# --- UTILIDADES ---
def normalizar_texto(texto):
    if not texto:
        return ''
    return ''.join(c for c in unicodedata.normalize('NFD', str(texto).lower()) if unicodedata.category(c) != 'Mn')

# --- VISTAS GENERALES (Lista, Crear Orden, Editar Orden, Eliminar Orden, API) ---
# ... (Mantener el código existente de lista_ordenes, crear_orden, editar_orden, eliminar_orden, buscar_cliente_api) ...
# (Para brevedad, asumo que mantienes el código previo aquí. Si necesitas que lo repita todo, dímelo).

@login_required
def lista_ordenes(request):
    ordenes = OrdenServicio.objects.all().select_related('cliente', 'tecnico_asignado', 'equipo').order_by('-fecha_creacion')
    filtro_estado = request.GET.get('estado')
    filtro_tecnico = request.GET.get('tecnico')
    filtro_prioridad = request.GET.get('prioridad')
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    
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

    paginator = Paginator(ordenes, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    tecnicos_list = User.objects.filter(groups__name='Técnico')
    
    context = {
        'page_obj': page_obj, 'tecnicos_list': tecnicos_list,
        'estados_opciones': OrdenServicio.ESTADO_OPCIONES, 'prioridades_opciones': OrdenServicio.PRIORIDAD_OPCIONES,
        'current_filters': {'estado': filtro_estado, 'tecnico': filtro_tecnico and int(filtro_tecnico) if filtro_tecnico else '', 'prioridad': filtro_prioridad, 'fecha_inicio': fecha_inicio, 'fecha_fin': fecha_fin}
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
            nueva_orden = OrdenServicio(cliente=cliente, equipo=equipo, descripcion_falla=descripcion, contrasena_equipo=contrasena, prioridad=prioridad, asistente_receptor=request.user, estado=OrdenServicio.ESTADO_NUEVA)
            if tecnico_id:
                nueva_orden.tecnico_asignado = User.objects.get(pk=tecnico_id)
            nueva_orden.save()
            messages.success(request, f'Orden #{nueva_orden.id} creada correctamente.')
            return redirect('lista_ordenes')

    tecnicos_list = User.objects.filter(groups__name='Técnico')
    prioridades = OrdenServicio.PRIORIDAD_OPCIONES
    cliente_pre = None
    equipos_pre = []
    if request.GET.get('cliente_id'):
        cliente_pre = get_object_or_404(Cliente, pk=request.GET.get('cliente_id'))
        equipos_pre = cliente_pre.equipos.all()

    context = {'tecnicos_list': tecnicos_list, 'prioridades': prioridades, 'cliente_pre': cliente_pre, 'equipos_pre': equipos_pre}
    return render(request, 'gestion_ordenes/crear_orden.html', context)

@login_required
@permission_required('gestion_ordenes.change_ordenservicio', raise_exception=True)
def editar_orden(request, orden_id):
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    if request.method == 'POST':
        orden.descripcion_falla = request.POST.get('descripcion_falla')
        orden.contrasena_equipo = request.POST.get('contrasena_equipo')
        orden.prioridad = request.POST.get('prioridad')
        orden.estado = request.POST.get('estado')
        tecnico_id = request.POST.get('tecnico_asignado')
        orden.tecnico_asignado = User.objects.get(pk=tecnico_id) if tecnico_id else None
        orden.save()
        messages.success(request, f'Orden #{orden.id} actualizada correctamente.')
        return redirect('lista_ordenes')

    tecnicos_list = User.objects.filter(groups__name='Técnico')
    prioridades = OrdenServicio.PRIORIDAD_OPCIONES
    estados = OrdenServicio.ESTADO_OPCIONES
    context = {'orden': orden, 'tecnicos_list': tecnicos_list, 'prioridades': prioridades, 'estados': estados}
    return render(request, 'gestion_ordenes/editar_orden.html', context)

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

# --- VISTAS DETALLE Y GESTIÓN ---

@login_required
def detalle_orden(request, orden_id):
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    cotizaciones = orden.cotizaciones.all().order_by('-id')
    bitacora = orden.bitacora.all().order_by('-fecha_hora')
    transferencias = orden.transferencias.all().select_related('usuario_solicitante', 'usuario_autoriza')
    form_servicio = AgregarServicioForm()

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
        'form_servicio': form_servicio,
    }
    return render(request, 'gestion_ordenes/detalle_orden.html', context)

@login_required
@permission_required('gestion_ordenes.change_ordenservicio', raise_exception=True)
@require_POST
def agregar_servicio_orden(request, orden_id):
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    form = AgregarServicioForm(request.POST)
    if form.is_valid():
        servicio = form.cleaned_data['servicio']
        if servicio in orden.servicios.all():
            messages.warning(request, f'El servicio "{servicio.nombre_servicio}" ya estaba agregado.')
        else:
            orden.servicios.add(servicio)
            BitacoraOrden.objects.create(orden=orden, usuario=request.user, descripcion=f"Se agregó el servicio: {servicio.nombre_servicio}")
            messages.success(request, f'Servicio "{servicio.nombre_servicio}" agregado correctamente.')
    else:
        messages.error(request, 'Error al agregar el servicio.')
    return redirect('detalle_orden', orden_id=orden_id)

@login_required
@permission_required('gestion_ordenes.change_ordenservicio', raise_exception=True)
def eliminar_servicio_orden(request, orden_id, servicio_id):
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    servicio = get_object_or_404(TipoServicio, pk=servicio_id)
    orden.servicios.remove(servicio)
    BitacoraOrden.objects.create(orden=orden, usuario=request.user, descripcion=f"Se eliminó el servicio: {servicio.nombre_servicio}")
    messages.success(request, f'Servicio "{servicio.nombre_servicio}" eliminado.')
    return redirect('detalle_orden', orden_id=orden_id)

# --- GESTIÓN DE COTIZACIONES (NUEVO) ---

@login_required
@permission_required('gestion_ordenes.add_cotizacion', raise_exception=True)
def crear_cotizacion(request, orden_id):
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    
    if request.method == 'POST':
        form = CotizacionForm(request.POST)
        if form.is_valid():
            cotizacion = form.save(commit=False)
            cotizacion.orden = orden
            cotizacion.usuario_creador = request.user
            cotizacion.save()
            
            # Bitácora
            BitacoraOrden.objects.create(
                orden=orden,
                usuario=request.user,
                descripcion=f"Se generó Cotización #{cotizacion.id}. Concepto: {cotizacion.concepto[:50]}..."
            )
            
            messages.success(request, 'Cotización registrada correctamente.')
            return redirect('detalle_orden', orden_id=orden.id)
    else:
        form = CotizacionForm()

    return render(request, 'gestion_ordenes/cotizacion_form.html', {'form': form, 'orden': orden})

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
            
            # Bitácora de cambios (si hubo cambio de estado)
            if estado_anterior != cotizacion.estado:
                BitacoraOrden.objects.create(
                    orden=orden,
                    usuario=request.user,
                    descripcion=f"Cotización #{cotizacion.id} cambió de estado: {estado_anterior} -> {cotizacion.estado}"
                )
            else:
                BitacoraOrden.objects.create(
                    orden=orden,
                    usuario=request.user,
                    descripcion=f"Se actualizó la Cotización #{cotizacion.id}"
                )

            messages.success(request, 'Cotización actualizada correctamente.')
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

# --- GESTIÓN DE TRANSFERENCIAS ---

@login_required
@permission_required('gestion_ordenes.add_transferencia', raise_exception=True)
def crear_transferencia(request, orden_id):
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    
    if request.method == 'POST':
        form = TransferenciaForm(request.POST)
        formset = ItemTransferidoFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            with transaction.atomic(): # Asegura que se guarde todo o nada
                # 1. Guardar Cabecera (Transferencia)
                transferencia = form.save(commit=False)
                transferencia.orden = orden
                transferencia.usuario_solicitante = request.user
                transferencia.save()
                
                # 2. Guardar Items
                formset.instance = transferencia
                formset.save()
                
                # 3. Bitácora
                BitacoraOrden.objects.create(
                    orden=orden,
                    usuario=request.user,
                    descripcion=f"Se solicitó Transferencia #{transferencia.id} al almacén."
                )
                
            messages.success(request, 'Solicitud de transferencia registrada correctamente.')
            return redirect('detalle_orden', orden_id=orden.id)
    else:
        form = TransferenciaForm()
        formset = ItemTransferidoFormSet()

    return render(request, 'gestion_ordenes/transferencia_form.html', {
        'form': form, 
        'formset': formset, 
        'orden': orden
    })

@login_required
@permission_required('gestion_ordenes.change_transferencia', raise_exception=True)
def editar_transferencia(request, orden_id, transferencia_id):
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    transferencia = get_object_or_404(Transferencia, pk=transferencia_id, orden=orden)
    
    # Bloquear edición si ya está autorizada (regla de negocio sugerida)
    if transferencia.usuario_autoriza and not request.user.groups.filter(name='Gerente Servicio').exists():
        messages.error(request, 'No se puede editar una transferencia ya autorizada.')
        return redirect('detalle_orden', orden_id=orden.id)

    if request.method == 'POST':
        form = TransferenciaForm(request.POST, instance=transferencia)
        formset = ItemTransferidoFormSet(request.POST, instance=transferencia)
        
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            
            # Lógica de Autorización (Solo si es Gerente y presionó el botón específico)
            if 'btn_autorizar' in request.POST and request.user.has_perm('gestion_ordenes.change_transferencia'):
                transferencia.usuario_autoriza = request.user
                transferencia.save()
                BitacoraOrden.objects.create(
                    orden=orden, usuario=request.user,
                    descripcion=f"Se AUTORIZÓ la Transferencia #{transferencia.id}"
                )
                messages.success(request, 'Transferencia actualizada y autorizada.')
            else:
                BitacoraOrden.objects.create(
                    orden=orden, usuario=request.user,
                    descripcion=f"Se actualizó la Transferencia #{transferencia.id}"
                )
                messages.success(request, 'Transferencia actualizada.')

            return redirect('detalle_orden', orden_id=orden.id)
    else:
        form = TransferenciaForm(instance=transferencia)
        formset = ItemTransferidoFormSet(instance=transferencia)

    return render(request, 'gestion_ordenes/transferencia_form.html', {
        'form': form, 
        'formset': formset, 
        'orden': orden,
        'transferencia': transferencia,
        'editar': True
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