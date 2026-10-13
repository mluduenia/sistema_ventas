# apps/ventas/afip_patch.py
import os
import tempfile
import pysimplesoap.client

# Guardar la función original
_original_fetch = pysimplesoap.client.fetch

def patched_fetch(url, cache=None, timeout=None, trace=False):
    """
    Versión parcheada de fetch que evita el problema de caracteres especiales en Windows.
    """
    # Si cache es una URL o contiene caracteres especiales, usar una carpeta temporal
    if cache and isinstance(cache, str):
        # Si contiene :// o caracteres no válidos para nombres de carpeta
        if '://' in cache or any(c in cache for c in ':*?"<>|'):
            # Usar una carpeta con nombre simple
            cache = os.path.join(tempfile.gettempdir(), 'afip_wsdl_cache')
            os.makedirs(cache, exist_ok=True)
    
    # Si no hay cache, usar una carpeta temporal
    if cache is None:
        cache = os.path.join(tempfile.gettempdir(), 'afip_wsdl_cache')
        os.makedirs(cache, exist_ok=True)
    
    # Llamar a la función original con el cache corregido
    return _original_fetch(url, cache, timeout, trace)

# Aplicar el parche
pysimplesoap.client.fetch = patched_fetch

print("✅ Parche de AFIP aplicado correctamente")