from django.urls import path
from . import views

app_name = 'configuracion'

urlpatterns = [
    # Aquí irán las URLs de configuración
    path('', views.configuracion_general, name='configuracion_general'),
]