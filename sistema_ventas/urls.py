from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

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

# Servir archivos media (logos, imágenes subidas)
# Nota: en producción ideal usar nginx/caddy, pero esto funciona para arrancar
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
