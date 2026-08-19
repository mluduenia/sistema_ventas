from django import forms
from .models import EmpresaConfig

class EmpresaConfigForm(forms.ModelForm):
    class Meta:
        model = EmpresaConfig
        fields = [
            'logo',  # 👈 Nuevo campo agregado al principio
            'razon_social',
            'nombre_fantasia',
            'cuit',
            'condicion_iva',
            'iibb',
            'inicio_actividades',
            'direccion',
            'telefono',
            'email',
            'email_smtp_host',
            'email_smtp_port',
            'email_smtp_user',
            'email_smtp_password',
            'email_smtp_use_tls',
            'punto_de_venta',
            'ambiente_arca',
            'certificado_crt',
            'clave_privada_key',
        ]
        widgets = {
            'logo': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}), # 👈 Widget con filtro para imágenes
            'razon_social': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'nombre_fantasia': forms.TextInput(attrs={'class': 'form-control'}),
            'cuit': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 20-12345678-9', 'required': True}),
            'condicion_iva': forms.Select(attrs={'class': 'form-select'}),
            'iibb': forms.TextInput(attrs={'class': 'form-control'}),
            'inicio_actividades': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            # SMTP
            'email_smtp_host': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'smtp.gmail.com'}),
            'email_smtp_port': forms.NumberInput(attrs={'class': 'form-control'}),
            'email_smtp_user': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'correo@miempresa.com'}),
            'email_smtp_password': forms.PasswordInput(attrs={'class': 'form-control', 'render_value': True, 'placeholder': '••••••••••••••••'}),
            'email_smtp_use_tls': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            # ARCA
            'punto_de_venta': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'ambiente_arca': forms.Select(attrs={'class': 'form-select'}),
            'certificado_crt': forms.FileInput(attrs={'class': 'form-control'}),
            'clave_privada_key': forms.FileInput(attrs={'class': 'form-control'}),
        }