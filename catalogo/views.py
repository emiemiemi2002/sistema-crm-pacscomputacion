from django.shortcuts import render
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from .models import Proveedor, TipoServicio

# --- VISTA PRINCIPAL (LISTA DOBLE) ---

class CatalogoListView(LoginRequiredMixin, ListView):
    """
    Vista principal que muestra tanto proveedores como tipos de servicio.
    Utiliza el modelo Proveedor como base, pero añade los tipos de servicio al contexto.
    """
    model = Proveedor
    template_name = 'catalogo/lista_catalogos.html'
    context_object_name = 'proveedores'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tipos_servicio'] = TipoServicio.objects.all()
        # Determinar qué pestaña abrir (por defecto 'proveedores')
        context['active_tab'] = self.request.GET.get('tab', 'proveedores')
        return context

# --- CRUD PROVEEDORES ---

class ProveedorCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Proveedor
    template_name = 'catalogo/proveedor_form.html'
    fields = ['nombre_empresa', 'persona_contacto', 'telefono', 'email']
    success_url = reverse_lazy('lista_catalogos')
    success_message = "Proveedor '%(nombre_empresa)s' creado correctamente."

    def get_success_url(self):
        return reverse_lazy('lista_catalogos') + '?tab=proveedores'

class ProveedorUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Proveedor
    template_name = 'catalogo/proveedor_form.html'
    fields = ['nombre_empresa', 'persona_contacto', 'telefono', 'email']
    success_message = "Proveedor '%(nombre_empresa)s' actualizado correctamente."

    def get_success_url(self):
        return reverse_lazy('lista_catalogos') + '?tab=proveedores'

class ProveedorDeleteView(LoginRequiredMixin, DeleteView):
    model = Proveedor
    template_name = 'catalogo/catalogo_confirm_delete.html'
    
    def get_success_url(self):
        messages.success(self.request, "Proveedor eliminado correctamente.")
        return reverse_lazy('lista_catalogos') + '?tab=proveedores'

# --- CRUD TIPOS DE SERVICIO ---

class TipoServicioCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = TipoServicio
    template_name = 'catalogo/tiposervicio_form.html'
    fields = ['nombre_servicio', 'costo_estandar', 'descripcion']
    success_message = "Servicio '%(nombre_servicio)s' creado correctamente."

    def get_success_url(self):
        return reverse_lazy('lista_catalogos') + '?tab=servicios'

class TipoServicioUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = TipoServicio
    template_name = 'catalogo/tiposervicio_form.html'
    fields = ['nombre_servicio', 'costo_estandar', 'descripcion']
    success_message = "Servicio '%(nombre_servicio)s' actualizado correctamente."

    def get_success_url(self):
        return reverse_lazy('lista_catalogos') + '?tab=servicios'

class TipoServicioDeleteView(LoginRequiredMixin, DeleteView):
    model = TipoServicio
    template_name = 'catalogo/catalogo_confirm_delete.html'

    def get_success_url(self):
        messages.success(self.request, "Tipo de servicio eliminado correctamente.")
        return reverse_lazy('lista_catalogos') + '?tab=servicios'