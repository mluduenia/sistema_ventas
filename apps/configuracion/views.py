from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import EmpresaConfig
from .forms import EmpresaConfigForm

@login_required
def configuracion_general(request):
    """Vista única para gestionar la configuración de la empresa y ARCA."""
    config, _ = EmpresaConfig.objects.get_or_create(id=1)

    if request.method == 'POST':
        form = EmpresaConfigForm(request.POST, request.FILES, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, 'La configuración de la empresa y datos de ARCA se han actualizado correctamente.')
            return redirect('configuracion:configuracion_general')
        else:
            messages.error(request, 'Por favor revisa los errores en el formulario.')
    else:
        form = EmpresaConfigForm(instance=config)

    return render(request, 'configuracion/empresa_config.html', {'form': form, 'config': config})

@login_required
def configuracion_view(request):
    config = EmpresaConfig.objects.first()

    if request.method == "POST":
        # Es FUNDAMENTAL incluir request.FILES para recibir los certificados
        form = EmpresaConfigForm(request.POST, request.FILES, instance=config)
        if form.is_validate():  # O form.is_valid()
            form.save()
            messages.success(request, "Configuración guardada correctamente.")
            return redirect("configuracion:index")  # O tu name de URL
        else:
            messages.error(
                request, "Error en el formulario. Revisa los datos."
            )
    else:
        form = EmpresaConfigForm(instance=config)

    return render(
        request, "configuracion/index.html", {"form": form, "config": config}
    )