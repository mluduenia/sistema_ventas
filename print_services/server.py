"""
Servicio local de impresión para el POS.
Permite configurar qué impresora usar para tickets y remitos desde /config.
Se levanta como servicio de Windows con NSSM.
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

from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS

# ============================================================
# CONFIGURACIÓN
# ============================================================

PUERTO = 8085

# 🔽 NUEVO: archivo de config persistente (impresoras elegidas)
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'print_config.json')

# Impresora por defecto (fallback si no hay nada configurado)
IMPRESORA_DEFAULT = os.environ.get('POS_PRINTER', 'POS80')

# 🔽 NUEVO: cantidad de líneas a avanzar antes de cortar
FEED_LINEAS = int(os.environ.get('POS_FEED_LINEAS', '8'))

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
# CONFIG: cargar/guardar impresoras
# ============================================================

def cargar_config():
    """Lee print_config.json o devuelve default."""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            'impresora_ticket': IMPRESORA_DEFAULT,
            'impresora_remito': IMPRESORA_DEFAULT,
        }

def guardar_config(config):
    """Guarda la config en print_config.json."""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

def obtener_impresora_por_tipo(tipo):
    """
    Devuelve el nombre de la impresora según el tipo de trabajo.
    tipo: 'ticket' | 'remito' | 'informe_z' | 'informe_x' | ...
    """
    config = cargar_config()
    if tipo == 'ticket' or tipo.startswith('informe_'):
        return config.get('impresora_ticket') or IMPRESORA_DEFAULT
    elif tipo == 'remito' or tipo == 'factura':
        return config.get('impresora_remito') or IMPRESORA_DEFAULT
    return config.get('impresora_ticket') or IMPRESORA_DEFAULT

# ============================================================
# RUTAS
# ============================================================

@app.route('/health', methods=['GET'])
def health():
    """Health check: verifica que el servicio está vivo."""
    config = cargar_config()
    return jsonify({
        'status': 'ok',
        'so': SO,
        'impresora_ticket': config.get('impresora_ticket'),
        'impresora_remito': config.get('impresora_remito'),
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
    """Verifica que la impresora esté instalada y disponible."""
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
                'error': f'Impresora "{IMPRESORA_DEFAULT}" no encontrada',
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


# ============================================================
# 🔽 NUEVO: UI DE CONFIGURACIÓN
# ============================================================

@app.route('/config', methods=['GET', 'POST'])
def configurar_impresoras():
    """UI para seleccionar impresoras de ticket y remito."""
    config = cargar_config()

    if request.method == 'POST':
        config['impresora_ticket'] = request.form.get('impresora_ticket', '')
        config['impresora_remito'] = request.form.get('impresora_remito', '')
        guardar_config(config)
        mensaje = "✅ Configuración guardada correctamente."
    else:
        mensaje = ""

    if SO == 'Windows':
        impresoras = listar_impresoras_windows()
    elif SO == 'Linux':
        impresoras = listar_impresoras_linux()
    else:
        impresoras = []

    html = '''
    <!DOCTYPE html>
    <html lang="es" data-bs-theme="light">
    <head>
        <meta charset="UTF-8">
        <title>Configurar Impresoras - Servicio POS</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    </head>
    <body class="p-4 bg-body-tertiary">
        <div class="container" style="max-width: 700px;">
            <div class="card shadow-lg border-0">
                <div class="card-header bg-primary text-white py-3">
                    <h4 class="mb-0">
                        <i class="fas fa-print me-2"></i> Configuración de Impresoras
                    </h4>
                </div>
                <div class="card-body p-4">

                    {% if mensaje %}
                    <div class="alert alert-success">
                        <i class="fas fa-check-circle me-1"></i> {{ mensaje }}
                    </div>
                    {% endif %}

                    <div class="alert alert-info small">
                        <i class="fas fa-info-circle me-1"></i>
                        Sistema operativo detectado: <strong>{{ so }}</strong><br>
                        Impresoras encontradas: <strong>{{ impresoras|length }}</strong>
                    </div>

                    <form method="POST">
                        <div class="mb-4">
                            <label class="form-label fw-bold">
                                <i class="fas fa-receipt text-primary me-1"></i>
                                Impresora para TICKETS (80mm)
                            </label>
                            <select name="impresora_ticket" class="form-select form-select-lg" required>
                                <option value="">-- Seleccionar --</option>
                                {% for imp in impresoras %}
                                <option value="{{ imp }}"
                                    {% if imp == config.impresora_ticket %}selected{% endif %}>
                                    {{ imp }}
                                </option>
                                {% endfor %}
                            </select>
                            <small class="text-muted">
                                Se usa para: tickets de venta, Cierre Z, Informe X.
                            </small>
                        </div>

                        <div class="mb-4">
                            <label class="form-label fw-bold">
                                <i class="fas fa-file-invoice text-warning me-1"></i>
                                Impresora para REMITOS / FACTURAS
                            </label>
                            <select name="impresora_remito" class="form-select form-select-lg" required>
                                <option value="">-- Seleccionar --</option>
                                {% for imp in impresoras %}
                                <option value="{{ imp }}"
                                    {% if imp == config.impresora_remito %}selected{% endif %}>
                                    {{ imp }}
                                </option>
                                {% endfor %}
                            </select>
                            <small class="text-muted">
                                Se usa para: remitos A4, facturas, presupuestos.
                            </small>
                        </div>

                        <button type="submit" class="btn btn-primary btn-lg w-100 fw-bold">
                            <i class="fas fa-save me-1"></i> Guardar Configuración
                        </button>
                    </form>

                    <hr class="my-4">

                    <div class="d-flex gap-2">
                        <a href="/printers" class="btn btn-outline-secondary flex-grow-1" target="_blank">
                            <i class="fas fa-list me-1"></i> Ver JSON de impresoras
                        </a>
                        <a href="/health" class="btn btn-outline-info flex-grow-1" target="_blank">
                            <i class="fas fa-heartbeat me-1"></i> Health check
                        </a>
                    </div>

                </div>
                <div class="card-footer text-muted small text-center">
                    Servicio local POS &mdash; {{ so }} &mdash; puerto {{ puerto }}
                </div>
            </div>
        </div>
    </body>
    </html>
    '''
    return render_template_string(
        html,
        config=config,
        impresoras=impresoras,
        so=SO,
        puerto=PUERTO,
        mensaje=mensaje,
    )


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
        modo = data.get('modo', 'html')

        # 🔽 CAMBIADO: usar config guardada según el tipo
        # Prioridad: 1) parámetro 'impresora' del JSON, 2) config según tipo, 3) default
        impresora = data.get('impresora') or obtener_impresora_por_tipo(tipo)

        if not contenido:
            return jsonify({'success': False, 'error': 'Falta "contenido"'}), 400

        if modo == 'texto':
            texto = contenido
        else:
            texto = html_a_texto(contenido)

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
            logger.info(f"Impreso OK: {tipo} ({len(texto)} chars) → {impresora}")
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
    """Convierte el HTML del ticket a texto plano."""
    html = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'</p>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'</div>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'</tr>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'</td>', '\t', html, flags=re.IGNORECASE)
    html = re.sub(r'<hr\s*/?>', '-' * 42 + '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'<[^>]+>', '', html)
    html = html.replace('&nbsp;', ' ')
    html = html.replace('&amp;', '&')
    html = html.replace('&lt;', '<')
    html = html.replace('&gt;', '>')
    html = html.replace('&quot;', '"')
    html = html.replace('&#39;', "'")
    html = re.sub(r'\n[ \t]+\n', '\n\n', html)
    html = re.sub(r'\n{3,}', '\n\n', html)
    return html.strip()


def listar_impresoras_windows():
    """Lista impresoras instaladas en Windows."""
    try:
        import win32print
        return [p[2] for p in win32print.EnumPrinters(2)]
    except ImportError:
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
    """Imprime en Windows usando el spooler (pywin32)."""
    try:
        import win32print

        INIT = b'\x1b\x40'
        CODEPAGE = b'\x1b\x74\x02'
        ALIGN_LEFT = b'\x1b\x61\x00'
        CUT = b'\x1d\x56\x41\x03'
        OPEN_DRAWER = b'\x1b\x70\x00\x19\xfa'

        FEED_ESC_POS = b'\x1b\x64' + bytes([FEED_LINEAS])

        buffer = INIT + CODEPAGE + ALIGN_LEFT

        if abrir_cajon:
            buffer += OPEN_DRAWER

        try:
            buffer += texto.encode('cp850', errors='replace')
        except Exception:
            buffer += texto.encode('utf-8', errors='replace')

        buffer += FEED_ESC_POS

        if cortar:
            buffer += CUT

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
    logger.info("=== Servicio de impresión POS ===")
    logger.info(f"Sistema operativo: {SO}")
    logger.info(f"Impresora por defecto: {IMPRESORA_DEFAULT}")
    logger.info(f"Feed antes de cortar: {FEED_LINEAS} líneas")
    logger.info(f"Config file: {CONFIG_FILE}")
    logger.info(f"Escuchando en: http://127.0.0.1:{PUERTO}")
    logger.info(f"Config UI:      http://127.0.0.1:{PUERTO}/config")
    logger.info(f"Health:         http://127.0.0.1:{PUERTO}/health")
    logger.info(f"=================================")

    app.run(
        host='127.0.0.1',
        port=PUERTO,
        debug=False,
    )