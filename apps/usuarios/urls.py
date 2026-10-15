from django.urls import path
from . import views

app_name = 'usuarios'

urlpatterns = [

    # ============================================================
    # AUTENTICACIÓN
    # ============================================================
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('perfil/', views.perfil_view, name='perfil'),

    # ============================================================
    # CRUD DE USUARIOS
    # ============================================================
    path('lista/', views.lista_usuarios_view, name='lista_usuarios'),
    path('crear/', views.crear_usuario_view, name='crear_usuario'),
    path('<int:usuario_id>/editar/', views.editar_usuario_view, name='editar_usuario'),
    path('<int:usuario_id>/baja/', views.dar_baja_usuario_view, name='dar_baja_usuario'),
    path('<int:usuario_id>/reactivar/', views.reactivar_usuario_view, name='reactivar_usuario'),

    # URL vieja (compatibilidad)
    path('gestion/', views.gestion_usuarios_view, name='gestion_usuarios'),
]