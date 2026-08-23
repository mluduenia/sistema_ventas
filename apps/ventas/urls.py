from django.urls import path
from . import views

app_name = 'ventas'

urlpatterns = [
    path('historial/', views.lista_ventas_view, name='lista_ventas'),
    path('pos/', views.pos_view, name='pos'),
    path('buscar-producto-ajax/', views.buscar_producto_ajax, name='buscar_producto_ajax'),
    path('procesar-venta-ajax/', views.procesar_venta_ajax, name='procesar_venta_ajax'),
    path('caja/abrir/', views.abrir_caja, name='abrir_caja'),
    path('caja/cerrar/', views.cerrar_caja, name='cerrar_caja'),
    path('cliente/crear/', views.crear_cliente, name='crear_cliente'),
    path('comprobante/<int:venta_id>/ticket/', views.comprobante_ticket, name='comprobante_ticket'),
    path('comprobante/<int:venta_id>/factura/', views.comprobante_factura, name='comprobante_factura'),
    path('enviar-email/<int:venta_id>/', views.enviar_email_comprobante, name='enviar_email_comprobante'),
    path('reportes/', views.reportes_view, name='reportes'),
]