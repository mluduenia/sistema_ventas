from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def configuracion_general(request):
    return render(request, 'configuracion/configuracion_general.html', {'titulo': 'Configuración'})