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
from django.db import transaction
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
    """
    Panel de Administración de Orden: Permite editar detalles operativos Y cerrar la orden.
    """
    orden = get_object_or_404(OrdenServicio, pk=orden_id)

    # 1. SI ESTÁ CERRADA: Modo Solo Lectura
    if orden.fecha_cierre:
        messages.error(request, "Esta orden ya se encuentra cerrada y no puede ser modificada.")
        return redirect('detalle_orden', orden_id=orden.id)

    # 2. Determinar permisos de edición
    es_finalizada = orden.estado == OrdenServicio.ESTADO_FINALIZADA_TECNICO
    puede_editar_tecnico = not es_finalizada
    puede_editar_prioridad = not es_finalizada

    if request.method == 'POST':
        accion = request.POST.get('accion')

        # --- CASO A: GUARDAR DETALLES ---
        if accion == 'guardar_detalles':
            cambios = []
            
            # Contraseña
            nueva_pass = request.POST.get('contrasena_equipo')
            if orden.contrasena_equipo != nueva_pass:
                orden.contrasena_equipo = nueva_pass
                cambios.append("Contraseña actualizada")

            # Prioridad
            if puede_editar_prioridad:
                nueva_prio = request.POST.get('prioridad')
                if orden.prioridad != nueva_prio:
                    orden.prioridad = nueva_prio
                    cambios.append(f"Prioridad: {nueva_prio}")

            # Técnico
            if puede_editar_tecnico:
                nuevo_tec_id = request.POST.get('tecnico_asignado')
                if nuevo_tec_id:
                    nuevo_tec = User.objects.get(pk=nuevo_tec_id)
                    if orden.tecnico_asignado != nuevo_tec:
                        orden.tecnico_asignado = nuevo_tec
                        cambios.append(f"Técnico: {nuevo_tec.username}")
                else:
                    if orden.tecnico_asignado:
                        orden.tecnico_asignado = None
                        cambios.append("Técnico desasignado")

            if cambios:
                orden.save()
                BitacoraOrden.objects.create(
                    orden=orden, usuario=request.user, 
                    descripcion=f"Edición administrativa: {', '.join(cambios)}"
                )
                messages.success(request, f"Detalles de la orden #{orden.id} actualizados.")
            else:
                messages.info(request, "No se detectaron cambios en los detalles.")
            
            # REDIRECCIÓN A LISTA
            return redirect('lista_ordenes')

        # --- CASO B: CERRAR ORDEN ---
        elif accion == 'cerrar_orden':
            user_groups = request.user.groups.values_list('name', flat=True)
            if not ('Gerente Servicio' in user_groups or 'Asistente Recepción' in user_groups or request.user.is_superuser):
                messages.error(request, "No tienes permisos para cerrar órdenes.")
                return redirect('editar_orden', orden_id=orden.id)

            nuevo_estado = request.POST.get('estado_cierre')
            
            if nuevo_estado == OrdenServicio.ESTADO_ENTREGADA and not es_finalizada:
                messages.error(request, "Error: No se puede entregar. El técnico aún no finaliza el servicio.")
            elif nuevo_estado == OrdenServicio.ESTADO_CANCELADA and es_finalizada:
                messages.error(request, "Error: No se puede cancelar. El servicio ya fue realizado.")
            elif nuevo_estado in [OrdenServicio.ESTADO_ENTREGADA, OrdenServicio.ESTADO_CANCELADA]:
                with transaction.atomic():
                    orden.estado = nuevo_estado
                    orden.fecha_cierre = timezone.now()
                    orden.save()
                    BitacoraOrden.objects.create(
                        orden=orden, usuario=request.user,
                        descripcion=f"*** ORDEN CERRADA - ESTADO: {nuevo_estado.upper()} ***"
                    )
                messages.success(request, f"Orden #{orden.id} cerrada exitosamente ({nuevo_estado}).")
                # REDIRECCIÓN A LISTA (SOLICITUD CUMPLIDA)
                return redirect('lista_ordenes')
            else:
                messages.error(request, "Estado de cierre no válido.")

    # --- PREPARACIÓN DEL CONTEXTO ---
    tecnicos_list = User.objects.filter(groups__name='Técnico')
    prioridades = OrdenServicio.PRIORIDAD_OPCIONES
    
    estados_cierre = []
    if es_finalizada:
        estados_cierre = [(OrdenServicio.ESTADO_ENTREGADA, 'Entregada al Cliente')]
    else:
        estados_cierre = [(OrdenServicio.ESTADO_CANCELADA, 'Cancelada')]

    context = {
        'orden': orden,
        'tecnicos_list': tecnicos_list,
        'prioridades': prioridades,
        'estados_cierre': estados_cierre,
        'puede_editar_tecnico': puede_editar_tecnico,
        'puede_editar_prioridad': puede_editar_prioridad,
        'es_finalizada': es_finalizada,
    }
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
@permission_required('gestion_ordenes.add_transferencia', raise_exception=True)
def crear_transferencia(request, orden_id):
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    if orden.fecha_cierre: return redirect('detalle_orden', orden_id=orden.id)
    
    ItemFormSet = inlineformset_factory(Transferencia, ItemTransferido, form=ItemTransferidoForm, extra=1, can_delete=True)

    if request.method == 'POST':
        form = TransferenciaForm(request.POST)
        formset = ItemFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            # FILTRO CRÍTICO: Contar ítems que tienen datos Y no están marcados para borrar
            valid_items = [
                f for f in formset 
                if f.cleaned_data and not f.cleaned_data.get('DELETE', False) and f.cleaned_data.get('descripcion_item')
            ]
            
            if not valid_items:
                messages.error(request, "No se puede guardar una transferencia sin ítems válidos.")
            else:
                with transaction.atomic():
                    trans = form.save(commit=False)
                    trans.orden = orden
                    trans.usuario_solicitante = request.user
                    trans.save()
                    formset.instance = trans
                    formset.save()
                    BitacoraOrden.objects.create(orden=orden, usuario=request.user, descripcion=f"Transferencia #{trans.id} solicitada.")
                messages.success(request, "Solicitud de transferencia enviada.")
                return redirect('detalle_orden', orden_id=orden.id)
    else:
        form = TransferenciaForm()
        formset = ItemFormSet(queryset=ItemTransferido.objects.none())

    return render(request, 'gestion_ordenes/transferencia_form.html', {'form': form, 'formset': formset, 'orden': orden})

@login_required
@permission_required('gestion_ordenes.change_transferencia', raise_exception=True)
def editar_transferencia(request, orden_id, transferencia_id):
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    transferencia = get_object_or_404(Transferencia, pk=transferencia_id, orden=orden)
    if orden.fecha_cierre: return redirect('detalle_orden', orden_id=orden.id)
    
    ItemFormSetEdit = inlineformset_factory(Transferencia, ItemTransferido, form=ItemTransferidoForm, extra=0, can_delete=True)

    if request.method == 'POST':
        form = TransferenciaForm(request.POST, instance=transferencia)
        formset = ItemFormSetEdit(request.POST, instance=transferencia)
        
        if form.is_valid() and formset.is_valid():
            # Verificación de ítems restantes después de posibles borrados
            valid_items = [
                f for f in formset 
                if f.cleaned_data and not f.cleaned_data.get('DELETE', False)
            ]
            
            if not valid_items:
                messages.error(request, "La transferencia debe contener al menos un ítem. No puede borrar todos los elementos.")
            else:
                form.save()
                formset.save()
                messages.success(request, "Transferencia actualizada.")
                return redirect('detalle_orden', orden_id=orden.id)
    else:
        form = TransferenciaForm(instance=transferencia)
        formset = ItemFormSetEdit(instance=transferencia)

    return render(request, 'gestion_ordenes/transferencia_form.html', {'form': form, 'formset': formset, 'orden': orden, 'transferencia': transferencia, 'editar': True})

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