from django.contrib import admin
from django.urls import path
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required

# Página de inicio
def home_view(request):
    context = {}
    return render(request, 'home.html', context)

# Dashboard (requiere login)
@login_required
def dashboard_view(request):
    return render(request, 'dashboard.html')

# Vista de login usando render
def login_view(request):
    # Si ya está autenticado, redirigir
    if request.user.is_authenticated:
        return redirect('/dashboard/')
    
    # Si es POST, procesar el login
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('/dashboard/')
        else:
            return render(request, 'usuarios/login.html', {'error': 'Usuario o contraseña incorrectos'})
    
    # Si es GET, mostrar el formulario
    return render(request, 'usuarios/login.html')

# Cerrar sesión
def logout_view(request):
    logout(request)
    return HttpResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Logout - Sistema de Ventas</title>
        <style>
            body { font-family: 'Segoe UI', Arial, sans-serif; max-width: 500px; margin: 100px auto; padding: 20px; }
            .container { background: #f5f6fa; padding: 40px; border-radius: 10px; text-align: center; }
            h1 { color: #2c3e50; }
            .btn { background: #3498db; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; }
            .btn:hover { background: #2980b9; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>👋 Sesión cerrada</h1>
            <p>Has cerrado sesión correctamente.</p>
            <a href="/" class="btn">Volver al inicio</a>
        </div>
    </body>
    </html>
    """)

# Perfil de usuario
@login_required
def perfil_view(request):
    return render(request, 'usuarios/perfil.html')

# URLs
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home_view, name='home'),
    path('dashboard/', dashboard_view, name='dashboard'),
    
    # URLs de usuarios
    path('usuarios/login/', login_view, name='login'),
    path('usuarios/logout/', logout_view, name='logout'),
    path('usuarios/perfil/', perfil_view, name='perfil'),
]