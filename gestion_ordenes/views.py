import unicodedata
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.utils.dateparse import parse_date
from django.utils import timezone
from django.db import transaction
from django.forms import inlineformset_factory

from gestion_clientes.models import Cliente, Equipo
from catalogo.models import TipoServicio
from .models import OrdenServicio, BitacoraOrden, Cotizacion, Transferencia, ItemTransferido
from .forms import (
    BitacoraForm, CotizacionForm, 
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

    if filtro_estado:
        ordenes = ordenes.filter(estado=filtro_estado)
    if filtro_tecnico:
        ordenes = ordenes.filter(tecnico_asignado__id=filtro_tecnico)
    if filtro_prioridad:
        ordenes = ordenes.filter(prioridad=filtro_prioridad)
    if fecha_inicio:
        ordenes = ordenes.filter(fecha_creacion__date__gte=parse_date(fecha_inicio))
    if fecha_fin:
        ordenes = ordenes.filter(fecha_creacion__date__lte=parse_date(fecha_fin))

    paginator = Paginator(ordenes, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    tecnicos = User.objects.filter(groups__name='Técnico') 
    
    context = {
        'page_obj': page_obj,
        'tecnicos': tecnicos,
        'estados': OrdenServicio.ESTADO_OPCIONES,
        'prioridades': OrdenServicio.PRIORIDAD_OPCIONES,
        'current_filters': request.GET
    }
    return render(request, 'gestion_ordenes/lista_ordenes.html', context)

@login_required
def buscar_cliente_api(request):
    query = request.GET.get('q', '').strip()
    if len(query) < 3:
        return JsonResponse({'resultados': []})
    
    q_norm = normalizar_texto(query)
    todos = Cliente.objects.all()[:50] 
    resultados = []

    for c in todos:
        if (q_norm in normalizar_texto(c.nombre_completo) or 
            q_norm in normalizar_texto(c.telefono)):
            
            equipos_data = []
            for eq in c.equipos.all():
                equipos_data.append({
                    'id': eq.id,
                    'tipo_equipo': eq.get_tipo_equipo_display(),
                    'marca': eq.marca,
                    'modelo': eq.modelo,
                    'numero_serie': eq.numero_serie
                })

            resultados.append({
                'id': c.id,
                'nombre': c.nombre_completo,
                'telefono': c.telefono,
                'equipos': equipos_data
            })
    
    return JsonResponse({'resultados': resultados})

@login_required
def crear_orden(request):
    cliente_pre = None
    equipos_pre = []
    
    if request.method == 'GET':
        cliente_id = request.GET.get('cliente_id')
        if cliente_id:
            cliente_pre = get_object_or_404(Cliente, pk=cliente_id)
            equipos_pre = cliente_pre.equipos.all()

    if request.method == 'POST':
        cliente_id = request.POST.get('cliente_id')
        equipo_id = request.POST.get('equipo_id')
        descripcion_falla = request.POST.get('descripcion_falla')
        prioridad = request.POST.get('prioridad')
        tecnico_id = request.POST.get('tecnico_asignado')
        
        contrasena_equipo = request.POST.get('contrasena_equipo', '').strip()

        if cliente_id and equipo_id and descripcion_falla:
            try:
                cliente = Cliente.objects.get(pk=cliente_id)
                equipo = Equipo.objects.get(pk=equipo_id)
                
                pass_actual = equipo.get_password() or ""
                
                if contrasena_equipo != pass_actual:
                    equipo.set_password(contrasena_equipo)
                    equipo.save()
                
                orden = OrdenServicio(
                    cliente=cliente,
                    equipo=equipo,
                    descripcion_falla=descripcion_falla,
                    prioridad=prioridad,
                    asistente_receptor=request.user
                )
                
                orden.contrasena_equipo = equipo.contrasena_equipo

                if tecnico_id:
                    orden.tecnico_asignado = User.objects.get(pk=tecnico_id)
                
                orden.save()
                
                BitacoraOrden.objects.create(
                    orden=orden,
                    usuario=request.user,
                    descripcion="Orden creada exitosamente."
                )

                messages.success(request, f'Orden #{orden.id} creada exitosamente.')
                return redirect('detalle_orden', orden_id=orden.id)
            except Exception as e:
                print(f"Error al crear orden: {e}") 
                messages.error(request, f'Error al crear orden: {e}')
        else:
            messages.error(request, 'Faltan datos obligatorios.')

    tecnicos = User.objects.filter(groups__name='Técnico')
    context = {
        'tecnicos_list': tecnicos,
        'prioridades': OrdenServicio.PRIORIDAD_OPCIONES,
        'cliente_pre': cliente_pre,
        'equipos_pre': equipos_pre
    }
    return render(request, 'gestion_ordenes/crear_orden.html', context)

@login_required
def detalle_orden(request, orden_id):
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    es_cerrada = (orden.fecha_cierre is not None)
    
    bitacora_form = BitacoraForm()
    
    cotizaciones = orden.cotizaciones.all().order_by('-fecha_creacion')
    transferencias = orden.transferencias.all().order_by('-fecha_transferencia')
    servicios_aplicados = orden.servicios.all()
    
    # CORRECCIÓN: Agregar catálogo de servicios al contexto
    servicios_catalogo = TipoServicio.objects.all().order_by('nombre_servicio')
    
    total_cotizado = sum(
        c.costo_total for c in cotizaciones 
        if c.estado == Cotizacion.ESTADO_AUTORIZADA
    )
    
    if request.method == 'POST' and 'btn_bitacora' in request.POST:
        form = BitacoraForm(request.POST)
        if form.is_valid():
            bitacora = form.save(commit=False)
            bitacora.orden = orden
            bitacora.usuario = request.user
            bitacora.save()
            messages.success(request, 'Nota agregada a la bitácora.')
            return redirect('detalle_orden', orden_id=orden.id)

    context = {
        'orden': orden,
        'es_cerrada': es_cerrada,
        'bitacora_form': bitacora_form,
        'cotizaciones': cotizaciones,
        'transferencias': transferencias,
        'servicios_aplicados': servicios_aplicados,
        'servicios_catalogo': servicios_catalogo, # Ahora sí disponible
        'total_cotizado': total_cotizado
    }
    return render(request, 'gestion_ordenes/detalle_orden.html', context)

# --- VISTA DE EDICIÓN ---

@login_required
@permission_required('gestion_ordenes.change_ordenservicio', raise_exception=True)
def editar_orden(request, orden_id):
    orden = get_object_or_404(OrdenServicio, pk=orden_id)

    if orden.fecha_cierre:
        messages.error(request, "Esta orden ya se encuentra cerrada y no puede ser modificada.")
        return redirect('detalle_orden', orden_id=orden.id)

    es_finalizada = orden.estado == OrdenServicio.ESTADO_FINALIZADA_TECNICO
    puede_editar_tecnico = not es_finalizada
    puede_editar_prioridad = not es_finalizada

    if request.method == 'POST':
        accion = request.POST.get('accion')

        if accion == 'guardar_detalles':
            cambios = []
            
            nueva_pass_raw = request.POST.get('contrasena_equipo', '').strip()
            pass_actual_plana = orden.equipo.get_password() or ''
            
            if nueva_pass_raw != pass_actual_plana:
                orden.equipo.set_password(nueva_pass_raw)
                orden.equipo.save()
                
                orden.contrasena_equipo = orden.equipo.contrasena_equipo
                
                if not nueva_pass_raw:
                     cambios.append("Contraseña eliminada del equipo")
                else:
                     cambios.append("Contraseña actualizada (Cifrada)")

            if puede_editar_prioridad:
                nueva_prio = request.POST.get('prioridad')
                if orden.prioridad != nueva_prio:
                    orden.prioridad = nueva_prio
                    cambios.append(f"Prioridad: {nueva_prio}")

            if puede_editar_tecnico:
                nuevo_tec_id = request.POST.get('tecnico_asignado')
                if nuevo_tec_id:
                    nuevo_tec = User.objects.get(pk=nuevo_tec_id)
                    if orden.tecnico_asignado != nuevo_tec:
                        orden.tecnico_asignado = nuevo_tec
                        cambios.append(f"Técnico: {nuevo_tec.username}")
                elif orden.tecnico_asignado:
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
            
            return redirect('lista_ordenes')

        elif accion == 'cerrar_orden':
            user_groups = request.user.groups.values_list('name', flat=True)
            if not ('Gerente Servicio' in user_groups or 'Asistente Recepción' in user_groups or request.user.is_superuser):
                messages.error(request, "No tienes permisos para cerrar órdenes.")
                return redirect('editar_orden', orden_id=orden.id)

            nuevo_estado = request.POST.get('estado_cierre')
            if nuevo_estado == OrdenServicio.ESTADO_ENTREGADA and not es_finalizada:
                messages.error(request, "No se puede entregar. El técnico no ha finalizado.")
            elif nuevo_estado == OrdenServicio.ESTADO_CANCELADA and es_finalizada:
                messages.error(request, "No se puede cancelar. El servicio ya fue realizado.")
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
                return redirect('lista_ordenes')

    if orden.contrasena_equipo:
         orden.contrasena_equipo = orden.equipo.get_password()

    tecnicos_list = User.objects.filter(groups__name='Técnico')
    prioridades = OrdenServicio.PRIORIDAD_OPCIONES
    estados_cierre = [(OrdenServicio.ESTADO_ENTREGADA, 'Entregada al Cliente')] if es_finalizada else [(OrdenServicio.ESTADO_CANCELADA, 'Cancelada')]

    return render(request, 'gestion_ordenes/editar_orden.html', {
        'orden': orden, 'tecnicos_list': tecnicos_list, 'prioridades': prioridades,
        'estados_cierre': estados_cierre, 'puede_editar_tecnico': puede_editar_tecnico,
        'puede_editar_prioridad': puede_editar_prioridad, 'es_finalizada': es_finalizada
    })

@login_required
@permission_required('gestion_ordenes.delete_ordenservicio', raise_exception=True)
def eliminar_orden(request, orden_id):
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    if request.method == 'POST':
        orden.delete()
        messages.success(request, 'Orden eliminada permanentemente.')
        return redirect('lista_ordenes')
    return render(request, 'gestion_ordenes/orden_confirm_delete.html', {'orden': orden})

# --- GESTIÓN DE SERVICIOS ADICIONALES ---

@login_required
def agregar_servicio_orden(request, orden_id):
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    if orden.fecha_cierre: return redirect('detalle_orden', orden_id=orden.id)
    
    if request.method == 'POST':
        servicio_id = request.POST.get('servicio_id')
        if servicio_id:
            servicio = get_object_or_404(TipoServicio, pk=servicio_id)
            orden.servicios.add(servicio)
            BitacoraOrden.objects.create(
                orden=orden, usuario=request.user,
                descripcion=f"Se agregó servicio: {servicio.nombre_servicio}"
            )
            messages.success(request, 'Servicio agregado.')
        return redirect('detalle_orden', orden_id=orden.id)
    
    return redirect('detalle_orden', orden_id=orden.id)

@login_required
def eliminar_servicio_orden(request, orden_id, servicio_id):
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    if orden.fecha_cierre: return redirect('detalle_orden', orden_id=orden.id)
    
    servicio = get_object_or_404(TipoServicio, pk=servicio_id)
    orden.servicios.remove(servicio)
    BitacoraOrden.objects.create(
        orden=orden, usuario=request.user,
        descripcion=f"Se eliminó servicio: {servicio.nombre_servicio}"
    )
    messages.warning(request, 'Servicio eliminado de la orden.')
    return redirect('detalle_orden', orden_id=orden.id)

# --- GESTIÓN DE COTIZACIONES ---

@login_required
def crear_cotizacion(request, orden_id):
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    if request.method == 'POST':
        form = CotizacionForm(request.POST)
        if form.is_valid():
            cotizacion = form.save(commit=False)
            cotizacion.orden = orden
            cotizacion.usuario_creador = request.user
            cotizacion.save()
            
            # CORRECCIÓN: Usar .costo_total (propiedad) en lugar de .total
            BitacoraOrden.objects.create(
                orden=orden, usuario=request.user,
                descripcion=f"Nueva cotización creada por ${cotizacion.costo_total}"
            )
            messages.success(request, 'Cotización creada exitosamente.')
            return redirect('detalle_orden', orden_id=orden.id)
    else:
        form = CotizacionForm()
    
    return render(request, 'gestion_ordenes/cotizacion_form.html', {'form': form, 'orden': orden, 'editar': False})

@login_required
def editar_cotizacion(request, orden_id, cotizacion_id):
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    cotizacion = get_object_or_404(Cotizacion, pk=cotizacion_id, orden=orden)
    
    if request.method == 'POST':
        form = CotizacionForm(request.POST, instance=cotizacion)
        if form.is_valid():
            form.save()
            BitacoraOrden.objects.create(
                orden=orden, usuario=request.user,
                descripcion=f"Actualización de cotización #{cotizacion.id}"
            )
            messages.success(request, 'Cotización actualizada.')
            return redirect('detalle_orden', orden_id=orden.id)
    else:
        form = CotizacionForm(instance=cotizacion)
    
    return render(request, 'gestion_ordenes/cotizacion_form.html', {'form': form, 'orden': orden, 'editar': True})

@login_required
def eliminar_cotizacion(request, orden_id, cotizacion_id):
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    cotizacion = get_object_or_404(Cotizacion, pk=cotizacion_id, orden=orden)
    
    if request.method == 'POST':
        cotizacion.delete()
        BitacoraOrden.objects.create(orden=orden, usuario=request.user, descripcion="Cotización eliminada")
        messages.success(request, 'Cotización eliminada.')
        return redirect('detalle_orden', orden_id=orden.id)
        
    return render(request, 'base.html')

# --- GESTIÓN DE TRANSFERENCIAS (MEJORADO CON AUTORIZACIÓN) ---

@login_required
def crear_transferencia(request, orden_id):
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    ItemFormSet = inlineformset_factory(Transferencia, ItemTransferido, form=ItemTransferidoForm, extra=1, can_delete=True)

    if request.method == 'POST':
        form = TransferenciaForm(request.POST)
        formset = ItemFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                transferencia = form.save(commit=False)
                transferencia.orden = orden
                transferencia.usuario_solicitante = request.user
                transferencia.save()
                
                formset.instance = transferencia
                formset.save()
                
                BitacoraOrden.objects.create(
                    orden=orden, usuario=request.user,
                    descripcion=f"Solicitud de transferencia (Ref: {transferencia.documento_referencia})"
                )
            
            messages.success(request, 'Transferencia registrada.')
            return redirect('detalle_orden', orden_id=orden.id)
    else:
        form = TransferenciaForm()
        formset = ItemFormSet()

    return render(request, 'gestion_ordenes/transferencia_form.html', {
        'orden': orden, 'form': form, 'formset': formset, 'editar': False
    })

@login_required
def editar_transferencia(request, orden_id, transferencia_id):
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    transferencia = get_object_or_404(Transferencia, pk=transferencia_id, orden=orden)
    ItemFormSet = inlineformset_factory(Transferencia, ItemTransferido, form=ItemTransferidoForm, extra=0, can_delete=True)

    if request.method == 'POST':
        # --- LÓGICA DE AUTORIZACIÓN ---
        if 'btn_autorizar' in request.POST:
            # 1. Verificar Rol (Recepción, Gerente o Superuser)
            user_groups = request.user.groups.values_list('name', flat=True)
            es_autorizador = 'Asistente Recepción' in user_groups or 'Gerente Servicio' in user_groups or request.user.is_superuser
            
            if not es_autorizador:
                messages.error(request, "No tienes permisos para autorizar transferencias.")
                return redirect('editar_transferencia', orden_id=orden.id, transferencia_id=transferencia.id)
            
            # 2. Verificar Conflicto de Interés
            if request.user == transferencia.usuario_solicitante:
                messages.error(request, "No puedes autorizar tu propia solicitud.")
                return redirect('editar_transferencia', orden_id=orden.id, transferencia_id=transferencia.id)

            # 3. Ejecutar Autorización
            with transaction.atomic():
                transferencia.usuario_autoriza = request.user
                transferencia.fecha_autorizacion = timezone.now()
                transferencia.save()
                
                BitacoraOrden.objects.create(
                    orden=orden, usuario=request.user,
                    descripcion=f"Transferencia #{transferencia.id} AUTORIZADA por {request.user.username}"
                )
            
            messages.success(request, f"Transferencia #{transferencia.id} autorizada correctamente.")
            return redirect('detalle_orden', orden_id=orden.id)

        # --- EDICIÓN NORMAL ---
        form = TransferenciaForm(request.POST, instance=transferencia)
        formset = ItemFormSet(request.POST, instance=transferencia)
        
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                form.save()
                formset.save()
                BitacoraOrden.objects.create(
                    orden=orden, usuario=request.user,
                    descripcion=f"Edición de transferencia #{transferencia.id}"
                )
            messages.success(request, 'Transferencia actualizada.')
            return redirect('detalle_orden', orden_id=orden.id)
    else:
        form = TransferenciaForm(instance=transferencia)
        formset = ItemFormSet(instance=transferencia)

    return render(request, 'gestion_ordenes/transferencia_form.html', {
        'orden': orden, 'form': form, 'formset': formset, 'editar': True, 
        'transferencia': transferencia # Pasamos el objeto para mostrar estado en template
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
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    if orden.fecha_cierre: return redirect('detalle_orden', orden_id=orden.id)
    
    nuevo_estado = request.POST.get('nuevo_estado')
    if nuevo_estado in dict(OrdenServicio.ESTADO_OPCIONES):
        anterior = orden.estado
        orden.estado = nuevo_estado
        orden.save()
        BitacoraOrden.objects.create(
            orden=orden, usuario=request.user,
            descripcion=f"Cambio de estado: {anterior} -> {nuevo_estado}"
        )
        messages.success(request, f'Estado actualizado a: {nuevo_estado}')
    
    return redirect('detalle_orden', orden_id=orden.id)

# --- BITÁCORA ---- 
@login_required
@permission_required('gestion_ordenes.change_bitacoraorden', raise_exception=True)
def editar_bitacora(request, orden_id, entrada_id):
    """
    Permite editar una entrada de bitácora existente.
    """
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    if orden.fecha_cierre:
        messages.error(request, "No se puede editar la bitácora de una orden cerrada.")
        return redirect('detalle_orden', orden_id=orden.id)

    entrada = get_object_or_404(BitacoraOrden, pk=entrada_id, orden=orden)

    if request.method == 'POST':
        nuevo_texto = request.POST.get('descripcion', '').strip()
        if nuevo_texto:
            entrada.descripcion = nuevo_texto
            entrada.save()
            messages.success(request, 'Nota de bitácora actualizada.')
        else:
            messages.warning(request, 'La nota no puede estar vacía.')
    
    return redirect('detalle_orden', orden_id=orden.id)

@login_required
@permission_required('gestion_ordenes.delete_bitacoraorden', raise_exception=True)
def eliminar_bitacora(request, orden_id, entrada_id):
    """
    Elimina una entrada de la bitácora.
    """
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    if orden.fecha_cierre:
        messages.error(request, "No se puede eliminar de una orden cerrada.")
        return redirect('detalle_orden', orden_id=orden.id)

    entrada = get_object_or_404(BitacoraOrden, pk=entrada_id, orden=orden)
    
    if request.method == 'POST':
        entrada.delete()
        messages.success(request, 'Nota de bitácora eliminada.')
    
    return redirect('detalle_orden', orden_id=orden.id)