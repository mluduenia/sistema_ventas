from django.contrib import admin
from django.urls import path, re_path, include
from django.conf import settings
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.core.urls')),
    path('ventas/', include('apps.ventas.urls')),
    path('productos/', include('apps.productos.urls')),
    path('usuarios/', include('apps.usuarios.urls')),
    path('configuracion/', include('apps.configuracion.urls')),
    path('session_security/', include('session_security.urls')),
    path('alertas/', include('apps.alertas.urls')),
]

# Servir archivos media (logos, imágenes subidas) incluso con DEBUG=False.
# Nota: para mejor rendimiento en producción, usar nginx/caddy.
re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
