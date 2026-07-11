from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def lista_ventas(request):
    return render(request, 'ventas/lista_ventas.html', {'titulo': 'Ventas'})