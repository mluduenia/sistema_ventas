from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from .forms import RegistroUsuarioForm

def login_view(request):
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'¡Bienvenido {username}!')
                return redirect('core:dashboard')
            else:
                messages.error(request, 'Usuario o contraseña incorrectos')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos')
    else:
        form = AuthenticationForm()
    
    return render(request, 'usuarios/login.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.info(request, 'Sesión cerrada correctamente')
    return redirect('usuarios:login')

@login_required
def perfil_view(request):
    return render(request, 'usuarios/perfil.html')

@login_required
def gestion_usuarios_view(request):
    if not request.user.is_superuser and request.user.rol != 'admin':
        messages.error(request, 'No tienes permiso para acceder a esta sección')
        return redirect('core:dashboard')
    
    from .models import Usuario
    usuarios = Usuario.objects.all()
    return render(request, 'usuarios/gestion_usuarios.html', {'usuarios': usuarios})