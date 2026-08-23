from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.core.urls')),  # Carga el Dashboard en la raíz
    path('ventas/', include('apps.ventas.urls')),
    path('productos/', include('apps.productos.urls')),
    path('usuarios/', include('apps.usuarios.urls')),
    path('configuracion/', include('apps.configuracion.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)