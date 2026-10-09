"""
Servicio local de impresión para el POS.
Imprime en impresora térmica POS80 conectada por USB (puerto USB003).
Usa el spooler de Windows vía pywin32.
"""
import os
import re
import sys
import json
import logging
import platform
import subprocess
import tempfile
from pathlib import Path

from flask import Flask, request, jsonify
from flask_cors import CORS

# ============================================================
# CONFIGURACIÓN
# ============================================================

# Puerto del servicio web (solo local)
PUERTO = 8085

# Nombre exacto de la impresora en Windows (el campo "Name" de Get-Printer)
IMPRESORA_DEFAULT = os.environ.get('POS_PRINTER', 'POS80')

# 🔽 NUEVO: Cantidad de líneas a avanzar antes de cortar el papel.
# Se puede ajustar sin tocar código con la variable de entorno POS_FEED_LINEAS.
#   4  → ~2 cm
#   6  → ~3 cm
#   8  → ~4 cm  ← recomendado (estándar comercial)
#   10 → ~5 cm
#   12 → ~6 cm
FEED_LINEAS = int(os.environ.get('POS_FEED_LINEAS', '8'))

# Sistema operativo
SO = platform.system()

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('print_service.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================
# APP FLASK
# ============================================================

app = Flask(__name__)

CORS(app, origins='*')

# ============================================================
# RUTAS
# ============================================================

@app.route('/health', methods=['GET'])
def health():
    """Health check: verifica que el servicio está vivo."""
    return jsonify({
        'status': 'ok',
        'so': SO,
        'impresora': IMPRESORA_DEFAULT,
        'metodo': 'USB (spooler Windows)',
        'feed_lineas': FEED_LINEAS,
    })


@app.route('/printers', methods=['GET'])
def listar_impresoras():
    """Lista las impresoras instaladas en el sistema."""
    try:
        if SO == 'Windows':
            impresoras = listar_impresoras_windows()
        elif SO == 'Linux':
            impresoras = listar_impresoras_linux()
        else:
            impresoras = []
        return jsonify({
            'success': True,
            'impresoras': impresoras,
            'default': IMPRESORA_DEFAULT,
        })
    except Exception as e:
        logger.exception("Error listando impresoras")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/test-connection', methods=['GET'])
def test_connection():
    """
    Verifica que la impresora esté instalada y disponible en Windows.
    """
    try:
        if SO != 'Windows':
            return jsonify({
                'success': False,
                'error': 'Este test solo funciona en Windows',
            })

        import win32print
        printers = [p[2] for p in win32print.EnumPrinters(2)]

        if IMPRESORA_DEFAULT in printers:
            handle = win32print.OpenPrinter(IMPRESORA_DEFAULT)
            info = win32print.GetPrinter(handle, 2)
            win32print.ClosePrinter(handle)

            return jsonify({
                'success': True,
                'message': f'Impresora "{IMPRESORA_DEFAULT}" está instalada y disponible',
                'status_code': info.get('Status', 0),
                'jobs_in_queue': info.get('cJobs', 0),
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Impresora "{IMPRESORA_DEFAULT}" no encontrada en Windows',
                'disponibles': printers,
            }), 404

    except ImportError:
        return jsonify({
            'success': False,
            'error': 'Falta instalar pywin32. Ejecutá: pip install pywin32',
        }), 500
    except Exception as e:
        logger.exception("Error en test-connection")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/print', methods=['POST'])
def imprimir():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Body vacío'}), 400

        contenido = data.get('contenido', '')
        tipo = data.get('tipo', 'ticket')
        cortar = data.get('cortar', True)
        abrir_cajon = data.get('abrir_cajon', False)
        modo = data.get('modo', 'html')  # 'html' o 'texto'

        # 🔽 NUEVO: definir la impresora (permite override desde el JS)
        impresora = data.get('impresora', IMPRESORA_DEFAULT)

        if not contenido:
            return jsonify({'success': False, 'error': 'Falta "contenido"'}), 400

        # 🔽 Si viene como texto plano, usarlo tal cual
        if modo == 'texto':
            texto = contenido
        else:
            texto = html_a_texto(contenido)

        # Imprimir según el SO
        if SO == 'Windows':
            resultado = imprimir_windows(texto, impresora, cortar, abrir_cajon)
        elif SO == 'Linux':
            resultado = imprimir_linux(texto, impresora)
        else:
            return jsonify({
                'success': False,
                'error': f'SO no soportado: {SO}',
            }), 400

        if resultado['success']:
            logger.info(f"Impreso OK: {tipo} ({len(texto)} caracteres) → {impresora}")
            return jsonify(resultado)
        else:
            return jsonify(resultado), 500

    except Exception as e:
        logger.exception("Error imprimiendo")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================
# UTILIDADES
# ============================================================

def html_a_texto(html):
    """
    Convierte el HTML del ticket a texto plano.
    """
    # Quitar scripts y estilos
    html = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)

    # Saltos de línea
    html = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'</p>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'</div>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'</tr>', '\n', html, flags=re.IGNORECASE)

    # Tabs para celdas
    html = re.sub(r'</td>', '\t', html, flags=re.IGNORECASE)

    # Líneas horizontales
    html = re.sub(r'<hr\s*/?>', '-' * 42 + '\n', html, flags=re.IGNORECASE)

    # Quitar tags restantes
    html = re.sub(r'<[^>]+>', '', html)

    # Entidades HTML
    html = html.replace('&nbsp;', ' ')
    html = html.replace('&amp;', '&')
    html = html.replace('&lt;', '<')
    html = html.replace('&gt;', '>')
    html = html.replace('&quot;', '"')
    html = html.replace('&#39;', "'")

    # Normalizar saltos múltiples
    html = re.sub(r'\n[ \t]+\n', '\n\n', html)
    html = re.sub(r'\n{3,}', '\n\n', html)

    return html.strip()


def listar_impresoras_windows():
    """Lista impresoras instaladas en Windows usando pywin32."""
    try:
        import win32print
        impresoras = [p[2] for p in win32print.EnumPrinters(2)]
        return impresoras
    except ImportError:
        # Fallback a wmic
        try:
            resultado = subprocess.run(
                ['wmic', 'printer', 'get', 'name'],
                capture_output=True, text=True, timeout=10
            )
            lineas = resultado.stdout.strip().split('\n')[1:]
            return [l.strip() for l in lineas if l.strip()]
        except Exception:
            return []
    except Exception as e:
        logger.error(f"Error listando impresoras: {e}")
        return []


def listar_impresoras_linux():
    """Lista impresoras instaladas en Linux."""
    try:
        resultado = subprocess.run(
            ['lpstat', '-p'],
            capture_output=True, text=True, timeout=10
        )
        impresoras = []
        for linea in resultado.stdout.strip().split('\n'):
            if linea.startswith('printer'):
                impresoras.append(linea.split()[1])
        return impresoras
    except Exception:
        return []


def imprimir_windows(texto, impresora, cortar=True, abrir_cajon=False):
    """
    Imprime en Windows usando el spooler (pywin32).
    Envía los comandos ESC/POS directamente al puerto.
    """
    try:
        import win32print

        # Comandos ESC/POS
        INIT = b'\x1b\x40'                     # Inicializar
        CODEPAGE = b'\x1b\x74\x02'             # Codepage CP850 (acentos/ñ)
        ALIGN_LEFT = b'\x1b\x61\x00'           # Alinear izquierda
        CUT = b'\x1d\x56\x41\x03'              # Cortar papel
        OPEN_DRAWER = b'\x1b\x70\x00\x19\xfa'  # Abrir cajón

        # 🔽 NUEVO: feed ESC/POS real (no depende del texto).
        # ESC d n → avanza n líneas físicas antes del corte.
        # Esto evita que el driver de Windows recorte los \n sobrantes.
        FEED_ESC_POS = b'\x1b\x64' + bytes([FEED_LINEAS])

        # Construir buffer ESC/POS
        buffer = INIT + CODEPAGE + ALIGN_LEFT

        if abrir_cajon:
            buffer += OPEN_DRAWER

        # Texto (codificar en CP850 para acentos y ñ)
        try:
            buffer += texto.encode('cp850', errors='replace')
        except Exception:
            buffer += texto.encode('utf-8', errors='replace')

        # 🔽 CAMBIADO: feed físico ESC/POS en lugar de '\n\n\n'
        buffer += FEED_ESC_POS

        if cortar:
            buffer += CUT

        # Abrir la impresora y enviar el trabajo como RAW
        handle = win32print.OpenPrinter(impresora)
        try:
            job_id = win32print.StartDocPrinter(
                handle, 1, ("Ticket POS", None, "RAW")
            )
            try:
                win32print.StartPagePrinter(handle)
                win32print.WritePrinter(handle, buffer)
                win32print.EndPagePrinter(handle)
            finally:
                win32print.EndDocPrinter(handle)
        finally:
            win32print.ClosePrinter(handle)

        return {
            'success': True,
            'message': f'Impreso en "{impresora}" (job #{job_id})',
            'job_id': job_id,
        }

    except ImportError:
        return {
            'success': False,
            'error': 'Falta instalar pywin32. Ejecutá: pip install pywin32',
        }
    except Exception as e:
        logger.exception("Error imprimiendo en Windows")
        return {'success': False, 'error': str(e)}


def imprimir_linux(texto, impresora):
    """Imprime en Linux usando el comando lp."""
    try:
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.txt', delete=False, encoding='utf-8'
        ) as f:
            f.write(texto)
            temp_path = f.name

        cmd = ['lp', '-o', 'raw']
        if impresora:
            cmd.extend(['-d', impresora])
        cmd.append(temp_path)

        resultado = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        try:
            os.unlink(temp_path)
        except Exception:
            pass

        if resultado.returncode == 0:
            return {'success': True, 'message': resultado.stdout.strip()}
        else:
            return {'success': False, 'error': resultado.stderr.strip()}

    except Exception as e:
        logger.exception("Error imprimiendo en Linux")
        return {'success': False, 'error': str(e)}


# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    logger.info(f"=== Servicio de impresión POS ===")
    logger.info(f"Sistema operativo: {SO}")
    logger.info(f"Impresora: {IMPRESORA_DEFAULT}")
    logger.info(f"Método: USB (spooler Windows)")
    logger.info(f"Feed antes de cortar: {FEED_LINEAS} líneas")
    logger.info(f"Escuchando en: http://127.0.0.1:{PUERTO}")
    logger.info(f"Health:        http://127.0.0.1:{PUERTO}/health")
    logger.info(f"Test:          http://127.0.0.1:{PUERTO}/test-connection")
    logger.info(f"Impresoras:    http://127.0.0.1:{PUERTO}/printers")
    logger.info(f"=================================")

    app.run(
        host='127.0.0.1',
        port=PUERTO,
        debug=False,
    )