from django.urls import path
from . import views

app_name = 'productos'

urlpatterns = [
    # Aquí irán las URLs de productos
    path('', views.lista_productos, name='lista_productos'),
]