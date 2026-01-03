import unicodedata
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import ProtectedError
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.urls import reverse
from .models import Cliente, Equipo

# --- UTILIDADES PARA BÚSQUEDA INTELIGENTE ---

def normalizar_texto(texto):
    """
    Convierte el texto a minúsculas y elimina acentos (tildes).
    Ejemplo: 'García' -> 'garcia', 'Árbol' -> 'arbol', 'Ana' -> 'ana'
    """
    if not texto:
        return ''
    # NFD separa los caracteres de sus tildes. 'Mn' es la categoría de marcas de acento.
    return ''.join(c for c in unicodedata.normalize('NFD', str(texto).lower()) if unicodedata.category(c) != 'Mn')

# --- VISTAS ---

@login_required
def lista_clientes(request):
    """
    Vista para listar clientes con búsqueda "Inteligente" en Python.
    Resuelve inconsistencias de acentos y mayúsculas.
    """
    query = request.GET.get('q', '').strip()
    
    # Obtenemos todos los clientes base (optimizamos trayendo solo lo necesario si fuera mucha data, 
    # pero para un CRM de residencia, traer los objetos completos está bien)
    todos_clientes = Cliente.objects.all().order_by('-fecha_registro')
    
    # Lista para almacenar los resultados filtrados
    clientes_filtrados = []

    if query:
        # 1. Normalizamos el término de búsqueda (input del usuario)
        query_norm = normalizar_texto(query)
        
        # 2. Iteramos y comparamos con datos normalizados
        # Esto asegura que "garcia" coincida con "García" almacenado en BD.
        for cliente in todos_clientes:
            # Normalizamos los campos del cliente para la comparación
            nombre_norm = normalizar_texto(cliente.nombre_completo)
            telefono_norm = normalizar_texto(cliente.telefono)
            email_norm = normalizar_texto(cliente.email)
            rfc_norm = normalizar_texto(cliente.rfc)
            
            # Verificamos si el término buscado está en alguno de los campos clave
            if (query_norm in nombre_norm or 
                query_norm in telefono_norm or 
                query_norm in email_norm or 
                query_norm in rfc_norm):
                clientes_filtrados.append(cliente)
    else:
        # Si no hay búsqueda, mostramos todos
        clientes_filtrados = todos_clientes

    # 3. Paginación (Usamos la lista filtrada)
    paginator = Paginator(clientes_filtrados, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'query': query,
    }
    return render(request, 'gestion_clientes/lista_clientes.html', context)

@login_required
def detalle_cliente(request, id):
    cliente = get_object_or_404(Cliente, pk=id)
    # Ordenar historial de más reciente a más antiguo
    historial_ordenes = cliente.ordenes.all().order_by('-fecha_creacion')
    equipos = cliente.equipos.all()

    context = {
        'cliente': cliente,
        'historial_ordenes': historial_ordenes,
        'equipos': equipos,
    }
    return render(request, 'gestion_clientes/detalle_cliente.html', context)

@login_required
def crear_equipo(request):
    """
    Vista para registrar un equipo.
    """
    cliente_pre = None
    cliente_id = request.GET.get('cliente_id')
    origen = request.GET.get('next', '') 

    if cliente_id:
        cliente_pre = get_object_or_404(Cliente, pk=cliente_id)

    if request.method == 'POST':
        cliente_id_post = request.POST.get('cliente_id')
        tipo = request.POST.get('tipo_equipo')
        marca = request.POST.get('marca')
        modelo = request.POST.get('modelo')
        serie = request.POST.get('serie')
        contrasena = request.POST.get('contrasena_equipo')
        
        origen_post = request.POST.get('next', '')

        if cliente_id_post and tipo and marca and modelo:
            cliente = get_object_or_404(Cliente, pk=cliente_id_post)
            
            nuevo_equipo = Equipo(
                cliente=cliente,
                tipo_equipo=tipo,
                marca=marca,
                modelo=modelo,
                numero_serie=serie
            )
            nuevo_equipo.set_password(contrasena)
            nuevo_equipo.save()
            
            messages.success(request, f'Equipo {marca} {modelo} registrado correctamente.')

            # --- LÓGICA DE RETORNO MEJORADA ---
            if origen_post == 'crear_orden':
                # MEJORA: Pasamos el ID del equipo creado para que se auto-seleccione
                url = reverse('crear_orden') + f'?cliente_id={cliente.id}&equipo_creado={nuevo_equipo.id}'
                return redirect(url)
            
            elif origen_post == 'detalle_cliente':
                return redirect('detalle_cliente', id=cliente.id)
            
            else:
                return redirect('detalle_cliente', id=cliente.id)
        else:
            messages.error(request, 'Por favor completa los campos obligatorios.')

    context = {
        'clientes_list': Cliente.objects.all().order_by('nombre_completo'),
        'tipos_equipo': Equipo.TIPO_EQUIPO_OPCIONES,
        'cliente_pre': cliente_pre,
        'next_url': origen
    }
    return render(request, 'gestion_clientes/crear_equipo.html', context)

@login_required
def crear_cliente(request):
    values = None
    if request.method == 'POST':
        nombre = request.POST.get('nombre_completo')
        telefono = request.POST.get('telefono')
        email = request.POST.get('email')
        rfc = request.POST.get('rfc')
        calle = request.POST.get('calle')
        num_ext = request.POST.get('numero_exterior')
        num_int = request.POST.get('numero_interior')
        colonia = request.POST.get('colonia')
        cp = request.POST.get('codigo_postal')
        ciudad = request.POST.get('ciudad')
        estado = request.POST.get('estado')

        values = request.POST

        if nombre and telefono:
            # Validación simple de teléfono único (aunque el modelo lo tiene, es mejor UX avisar aquí)
            if Cliente.objects.filter(telefono=telefono).exists():
                messages.error(request, 'Ya existe un cliente con ese número de teléfono.')
                return render(request, 'gestion_clientes/cliente_form.html', {'values': values})

            nuevo_cliente = Cliente(
                nombre_completo=nombre, telefono=telefono, email=email, rfc=rfc,
                calle=calle, numero_exterior=num_ext, numero_interior=num_int,
                colonia=colonia, codigo_postal=cp, ciudad=ciudad, estado=estado
            )
            nuevo_cliente.save()
            messages.success(request, f'Cliente "{nombre}" creado exitosamente.')
            return redirect('detalle_cliente', id=nuevo_cliente.id)
        else:
            messages.error(request, 'Por favor completa los campos obligatorios (*).')

    return render(request, 'gestion_clientes/cliente_form.html', {'values': values})

@login_required
def editar_cliente(request, id):
    cliente = get_object_or_404(Cliente, pk=id)
    if request.method == 'POST':
        cliente.nombre_completo = request.POST.get('nombre_completo')
        cliente.telefono = request.POST.get('telefono')
        cliente.email = request.POST.get('email')
        cliente.rfc = request.POST.get('rfc')
        cliente.calle = request.POST.get('calle')
        cliente.numero_exterior = request.POST.get('numero_exterior')
        cliente.numero_interior = request.POST.get('numero_interior')
        cliente.colonia = request.POST.get('colonia')
        cliente.codigo_postal = request.POST.get('codigo_postal')
        cliente.ciudad = request.POST.get('ciudad')
        cliente.estado = request.POST.get('estado')

        if cliente.nombre_completo and cliente.telefono:
            cliente.save()
            messages.success(request, 'Información del cliente actualizada correctamente.')
            return redirect('detalle_cliente', id=cliente.id)
        else:
            messages.error(request, 'El nombre y teléfono no pueden estar vacíos.')

    return render(request, 'gestion_clientes/cliente_form.html', {'cliente': cliente})

@login_required
@permission_required('gestion_clientes.delete_cliente', raise_exception=True)
def eliminar_cliente(request, id):
    """
    Vista para eliminar un cliente. Requiere permiso de Gerente.
    """
    cliente = get_object_or_404(Cliente, pk=id)

    if request.method == 'POST':
        try:
            nombre = cliente.nombre_completo
            cliente.delete()
            messages.success(request, f'Cliente "{nombre}" eliminado correctamente.')
            return redirect('lista_clientes')
        except ProtectedError:
            messages.error(request, f'No se puede eliminar a "{cliente.nombre_completo}" porque tiene historial de Órdenes de Servicio o Equipos activos.')
            return redirect('detalle_cliente', id=cliente.id)

    return render(request, 'gestion_clientes/cliente_confirm_delete.html', {'cliente': cliente})

@login_required
def obtener_password_equipo_api(request, equipo_id):
    """
    API interna para obtener la contraseña desencriptada de un equipo.
    Usada en crear_orden vía AJAX.
    """
    equipo = get_object_or_404(Equipo, pk=equipo_id)
    # Reutilizamos tu método get_password del modelo
    password_plana = equipo.get_password() 
    
    return JsonResponse({
        'id': equipo.id,
        'password': password_plana if password_plana else ''
    })

# --- GESTIÓN DE EQUIPOS ---

@login_required
@permission_required('gestion_clientes.change_equipo', raise_exception=True)
def editar_equipo(request, pk):
    """
    Permite editar los datos de un equipo existente.
    Reutiliza la plantilla crear_equipo.html.
    """
    equipo = get_object_or_404(Equipo, pk=pk)
    
    if request.method == 'POST':
        # Captura de datos
        tipo = request.POST.get('tipo_equipo')
        marca = request.POST.get('marca')
        modelo = request.POST.get('modelo')
        serie = request.POST.get('serie')
        contrasena = request.POST.get('contrasena_equipo', '').strip()
        
        if tipo and marca and modelo:
            equipo.tipo_equipo = tipo
            equipo.marca = marca
            equipo.modelo = modelo
            equipo.numero_serie = serie
            
            # Solo actualizamos contraseña si se escribió algo diferente a la actual
            pass_actual = equipo.get_password() or ""
            if contrasena != pass_actual:
                equipo.set_password(contrasena)
            
            equipo.save()
            messages.success(request, f'Equipo {marca} {modelo} actualizado correctamente.')
            return redirect('detalle_cliente', id=equipo.cliente.id)
        else:
            messages.error(request, 'Completa los campos obligatorios.')

    # Contexto para pre-llenar el formulario
    context = {
        'equipo': equipo, # Objeto clave para modo edición
        'cliente_pre': equipo.cliente,
        'tipos_equipo': Equipo.TIPO_EQUIPO_OPCIONES,
        'clientes_list': Cliente.objects.all(), # Por si se quisiera cambiar dueño (opcional)
        'editar': True 
    }
    return render(request, 'gestion_clientes/crear_equipo.html', context)

@login_required
@permission_required('gestion_clientes.delete_equipo', raise_exception=True)
def eliminar_equipo(request, pk):
    """
    Elimina un equipo. Requiere permisos de nivel Gerente (delete_equipo).
    """
    equipo = get_object_or_404(Equipo, pk=pk)
    cliente_id = equipo.cliente.id
    
    if request.method == 'POST':
        try:
            nombre_equipo = f"{equipo.tipo_equipo} {equipo.marca}"
            equipo.delete()
            messages.success(request, f'Equipo {nombre_equipo} eliminado.')
            return redirect('detalle_cliente', id=cliente_id)
        except ProtectedError:
            messages.error(request, "No se puede eliminar este equipo porque tiene órdenes de servicio asociadas.")
            return redirect('detalle_cliente', id=cliente_id)
            
    return render(request, 'gestion_clientes/equipo_confirm_delete.html', {'equipo': equipo})
