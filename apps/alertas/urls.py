from django.urls import path
from . import views

app_name = 'alertas'

urlpatterns = [
    path('<int:alerta_id>/marcar-leida/', views.marcar_alerta_leida, name='marcar_leida'),
]