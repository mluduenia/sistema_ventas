from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.core.paginator import Paginator
from django.db.models import Q
from functools import wraps

from .forms import RegistroUsuarioForm
from .models import Usuario, PermisoTemporal
from apps.configuracion.models import Sucursal


# ============================================================
# DECORADOR: SOLO ADMIN / GERENTE
# ============================================================
def solo_admin_gerente(view_func):
    """Solo permite acceso a admin/gerente/superuser."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('usuarios:login')
        if not request.user.puede_gestionar_usuarios:
            messages.error(request, 'No tenés permisos para gestionar usuarios.')
            return redirect('core:dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped


# ============================================================
# AUTENTICACIÓN
# ============================================================
def login_view(request):
    """Inicio de sesión."""
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                if not user.activo:
                    messages.error(request, 'Tu usuario está desactivado. Contactá al administrador.')
                    return render(request, 'usuarios/login.html', {'form': form})

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
    """Cierre de sesión."""
    logout(request)
    messages.info(request, 'Sesión cerrada correctamente')
    return redirect('usuarios:login')


# ============================================================
# PERFIL
# ============================================================
@login_required
def perfil_view(request):
    """Ver perfil propio."""
    return render(request, 'usuarios/perfil.html')


# ============================================================
# LISTA DE USUARIOS
# ============================================================
@login_required
@solo_admin_gerente
def lista_usuarios_view(request):
    """Lista todos los usuarios con filtro por rol, estado y búsqueda."""

    busqueda = request.GET.get('q', '').strip()
    rol_filtro = request.GET.get('rol', '').strip()
    estado = request.GET.get('estado', '1')
    sucursal_id = request.GET.get('sucursal', '').strip()

    usuarios = Usuario.objects.select_related('sucursal').all().order_by(
        '-activo', 'rol', 'first_name', 'last_name'
    )

    # Filtros
    if rol_filtro:
        usuarios = usuarios.filter(rol=rol_filtro)

    if estado == '1':
        usuarios = usuarios.filter(activo=True)
    elif estado == '0':
        usuarios = usuarios.filter(activo=False)

    if sucursal_id:
        usuarios = usuarios.filter(sucursal_id=sucursal_id)

    if busqueda:
        usuarios = usuarios.filter(
            Q(username__icontains=busqueda) |
            Q(first_name__icontains=busqueda) |
            Q(last_name__icontains=busqueda) |
            Q(email__icontains=busqueda) |
            Q(telefono__icontains=busqueda)
        )

    # KPIs por rol
    total_activos = Usuario.objects.filter(activo=True).count()
    total_por_rol = {}
    for codigo, label in Usuario.ROLES:
        total_por_rol[codigo] = {
            'label': label,
            'cantidad': Usuario.objects.filter(rol=codigo, activo=True).count(),
        }

    # Paginación
    paginator = Paginator(usuarios, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'busqueda': busqueda,
        'rol_filtro': rol_filtro,
        'estado': estado,
        'sucursal_id': sucursal_id,
        'roles_disponibles': Usuario.ROLES,
        'sucursales_disponibles': Sucursal.objects.filter(activa=True).order_by('nombre'),
        'total_activos': total_activos,
        'total_por_rol': total_por_rol,
    }
    return render(request, 'usuarios/lista_usuarios.html', context)


# ============================================================
# CREAR USUARIO
# ============================================================
@login_required
@solo_admin_gerente
def crear_usuario_view(request):
    """Crea un nuevo usuario."""

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        password2 = request.POST.get('password2', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        direccion = request.POST.get('direccion', '').strip()
        rol = request.POST.get('rol', 'vendedor')
        sucursal_id = request.POST.get('sucursal') or None
        activo = request.POST.get('activo') == 'on'

        # Validaciones
        errores = []
        if not username:
            errores.append('El nombre de usuario es obligatorio.')
        elif Usuario.objects.filter(username=username).exists():
            errores.append(f'El username "{username}" ya está en uso.')

        if not password:
            errores.append('La contraseña es obligatoria.')
        elif password != password2:
            errores.append('Las contraseñas no coinciden.')
        elif len(password) < 6:
            errores.append('La contraseña debe tener al menos 6 caracteres.')

        if not first_name:
            errores.append('El nombre es obligatorio.')

        if rol not in [r[0] for r in Usuario.ROLES]:
            errores.append('Rol inválido.')

        if errores:
            for err in errores:
                messages.error(request, err)
            return render(request, 'usuarios/crear_usuario.html', {
                'form_data': request.POST,
                'roles_disponibles': Usuario.ROLES,
                'sucursales': Sucursal.objects.filter(activa=True).order_by('nombre'),
            })

        # Crear usuario
        try:
            usuario = Usuario.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                telefono=telefono,
                direccion=direccion,
                rol=rol,
                sucursal_id=sucursal_id,
                activo=activo,
                is_active=activo,
            )
            messages.success(request, f'Usuario "{username}" creado correctamente.')
            return redirect('usuarios:lista_usuarios')

        except Exception as e:
            messages.error(request, f'Error al crear el usuario: {str(e)}')
            return render(request, 'usuarios/crear_usuario.html', {
                'form_data': request.POST,
                'roles_disponibles': Usuario.ROLES,
                'sucursales': Sucursal.objects.filter(activa=True).order_by('nombre'),
            })

    context = {
        'roles_disponibles': Usuario.ROLES,
        'sucursales': Sucursal.objects.filter(activa=True).order_by('nombre'),
    }
    return render(request, 'usuarios/crear_usuario.html', context)


# ============================================================
# EDITAR USUARIO
# ============================================================
@login_required
@solo_admin_gerente
def editar_usuario_view(request, usuario_id):
    """Edita un usuario existente."""

    usuario = get_object_or_404(Usuario, id=usuario_id)

    # No permitir que un gerente edite a un admin (a menos que sea superuser)
    if usuario.rol == 'admin' and not request.user.is_superuser:
        messages.error(request, 'Solo un superusuario puede editar a un administrador.')
        return redirect('usuarios:lista_usuarios')

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        direccion = request.POST.get('direccion', '').strip()
        rol = request.POST.get('rol', usuario.rol)
        sucursal_id = request.POST.get('sucursal') or None
        activo = request.POST.get('activo') == 'on'
        nueva_password = request.POST.get('password', '').strip()
        password2 = request.POST.get('password2', '').strip()

        errores = []
        if not first_name:
            errores.append('El nombre es obligatorio.')

        if rol not in [r[0] for r in Usuario.ROLES]:
            errores.append('Rol inválido.')

        if nueva_password:
            if nueva_password != password2:
                errores.append('Las contraseñas no coinciden.')
            elif len(nueva_password) < 6:
                errores.append('La contraseña debe tener al menos 6 caracteres.')

        if errores:
            for err in errores:
                messages.error(request, err)
            return render(request, 'usuarios/editar_usuario.html', {
                'usuario_obj': usuario,
                'roles_disponibles': Usuario.ROLES,
                'sucursales': Sucursal.objects.filter(activa=True).order_by('nombre'),
            })

        # Actualizar
        usuario.first_name = first_name
        usuario.last_name = last_name
        usuario.email = email
        usuario.telefono = telefono
        usuario.direccion = direccion
        usuario.rol = rol
        usuario.sucursal_id = sucursal_id
        usuario.activo = activo
        usuario.is_active = activo

        if nueva_password:
            usuario.set_password(nueva_password)

        usuario.save()
        messages.success(request, f'Usuario "{usuario.username}" actualizado correctamente.')
        return redirect('usuarios:lista_usuarios')

    context = {
        'usuario_obj': usuario,
        'roles_disponibles': Usuario.ROLES,
        'sucursales': Sucursal.objects.filter(activa=True).order_by('nombre'),
    }
    return render(request, 'usuarios/editar_usuario.html', context)


# ============================================================
# BAJA / REACTIVACIÓN (soft delete)
# ============================================================
@login_required
@solo_admin_gerente
def dar_baja_usuario_view(request, usuario_id):
    """Da de baja a un usuario (soft delete)."""
    if request.method != 'POST':
        return redirect('usuarios:lista_usuarios')

    usuario = get_object_or_404(Usuario, id=usuario_id)

    if usuario.rol == 'admin' and not request.user.is_superuser:
        messages.error(request, 'Solo un superusuario puede dar de baja a un administrador.')
        return redirect('usuarios:lista_usuarios')

    if usuario == request.user:
        messages.error(request, 'No podés darte de baja a vos mismo.')
        return redirect('usuarios:lista_usuarios')

    usuario.activo = False
    usuario.is_active = False
    usuario.save()
    messages.success(request, f'Usuario "{usuario.username}" dado de baja.')

    return redirect('usuarios:lista_usuarios')


@login_required
@solo_admin_gerente
def reactivar_usuario_view(request, usuario_id):
    """Reactiva un usuario."""
    if request.method != 'POST':
        return redirect('usuarios:lista_usuarios')

    usuario = get_object_or_404(Usuario, id=usuario_id)
    usuario.activo = True
    usuario.is_active = True
    usuario.save()
    messages.success(request, f'Usuario "{usuario.username}" reactivado.')

    return redirect('usuarios:lista_usuarios')


# ============================================================
# GESTIÓN DE USUARIOS (compatibilidad con la URL vieja)
# ============================================================
@login_required
def gestion_usuarios_view(request):
    """Redirige a la lista nueva de usuarios."""
    return redirect('usuarios:lista_usuarios')