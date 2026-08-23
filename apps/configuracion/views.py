from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import EmpresaConfig
from .forms import EmpresaConfigForm


def es_admin_o_super(user):
    """Permite el acceso a Superusuarios o Administradores."""
    return user.is_authenticated and (
        user.is_superuser or user.groups.filter(name='Administrador').exists()
    )


@login_required
@user_passes_test(es_admin_o_super)
def configuracion_general(request):
    """Vista única para gestionar la configuración de la empresa y ARCA."""
    config, _ = EmpresaConfig.objects.get_or_create(id=1)

    if request.method == 'POST':
        # Bloqueo explícito: Solo el Superusuario puede guardar los cambios
        if not request.user.is_superuser:
            messages.error(
                request, 
                'Acceso denegado: Tienes permisos de lectura. Solo el Superusuario puede modificar la configuración.'
            )
            return redirect('configuracion:configuracion_general')

        form = EmpresaConfigForm(request.POST, request.FILES, instance=config)
        if form.is_valid():
            form.save()
            messages.success(
                request, 
                'La configuración de la empresa y datos de ARCA se han actualizado correctamente.'
            )
            return redirect('configuracion:configuracion_general')
        else:
            messages.error(request, 'Por favor revisa los errores en el formulario.')
    else:
        form = EmpresaConfigForm(instance=config)

    return render(
        request, 
        'configuracion/empresa_config.html', 
        {
            'form': form, 
            'config': config,
            'es_readonly': not request.user.is_superuser  # Bandera útil para deshabilitar campos en el HTML
        }
    )