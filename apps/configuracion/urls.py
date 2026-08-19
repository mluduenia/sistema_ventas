from django.urls import path
from . import views

app_name = 'configuracion'

urlpatterns = [
    # Ruta principal usando el nombre exacto de tu vista
    path('', views.configuracion_general, name='configuracion_general'),
    
    # Alias de respaldo para compatibilidad
    path('index/', views.configuracion_general, name='index'),
]