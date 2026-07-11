from django.urls import path
from . import views

app_name = 'ventas'

urlpatterns = [
    # Aquí irán las URLs de ventas
    path('', views.lista_ventas, name='lista_ventas'),
]