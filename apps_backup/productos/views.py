from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def lista_productos(request):
    return render(request, 'productos/lista_productos.html', {'titulo': 'Productos'})