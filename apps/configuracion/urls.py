from django.urls import path
from . import views

app_name = 'configuracion'

urlpatterns = [
    # Ruta principal usando el nombre exacto de tu vista
    path('', views.configuracion_general, name='configuracion_general'),
    path('sucursales/', views.lista_sucursales_view, name='lista_sucursales'),
    path('sucursales/crear/', views.crear_sucursal_view, name='crear_sucursal'),
    path('sucursales/<int:sucursal_id>/editar/', views.editar_sucursal_view, name='editar_sucursal'),
    path('sucursales/stock/', views.stock_por_sucursal_view, name='stock_por_sucursal'),
    path('modulos/', views.modulos_negocio_view, name='modulos_negocio'),
    path('limpiar-datos/', views.limpiar_datos_view, name='limpiar_datos'),
    path('limpiar-datos/ejecutar/', views.ejecutar_limpieza_view, name='ejecutar_limpieza'),
    path('reset-dev/', views.reset_dev_view, name='reset_dev'),
    path('reset-dev/ejecutar/', views.ejecutar_reset_dev_view, name='ejecutar_reset_dev'),
    path('auditoria/', views.auditoria_view, name='auditoria'),
    path('auditoria/<int:log_id>/', views.auditoria_detalle_view, name='auditoria_detalle'),
]