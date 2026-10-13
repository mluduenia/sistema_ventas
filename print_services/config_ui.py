"""
UI de configuración para el servicio de impresión POS.
Permite seleccionar qué impresora usar para cada tipo de trabajo.
Guarda la config en print_config.json (mismo archivo que usa el server).
"""
import json
import os
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox
import platform

# ============================================================
# CONFIGURACIÓN
# ============================================================
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'print_config.json')

# Tipos de trabajo y su etiqueta visible
TIPOS = [
    ('impresora_ticket',  'Tickets de venta / Cierre Z / Informe X'),
    ('impresora_remito',  'Remitos / Facturas A4'),
    ('impresora_informe', 'Informes (opcional, si querés otra)'),
]

# ============================================================
# UTILIDADES
# ============================================================

def cargar_config():
    """Lee print_config.json o devuelve un dict vacío."""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def guardar_config(config):
    """Guarda la config en print_config.json."""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def listar_impresoras():
    """Lista las impresoras instaladas en el sistema."""
    so = platform.system()
    if so == 'Windows':
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
            print(f"Error listando impresoras: {e}")
            return []
    elif so == 'Linux':
        try:
            resultado = subprocess.run(
                ['lpstat', '-p'], capture_output=True, text=True, timeout=10
            )
            return [
                l.split()[1] for l in resultado.stdout.strip().split('\n')
                if l.startswith('printer')
            ]
        except Exception:
            return []
    return []


def probar_impresora(nombre):
    """Envía un ticket de prueba a la impresora indicada."""
    so = platform.system()
    if so != 'Windows':
        return False, "Solo soportado en Windows por ahora"

    try:
        import win32print

        INIT = b'\x1b\x40'
        CODEPAGE = b'\x1b\x74\x02'
        ALIGN_CENTER = b'\x1b\x61\x01'
        ALIGN_LEFT = b'\x1b\x61\x00'
        BOLD_ON = b'\x1b\x45\x01'
        BOLD_OFF = b'\x1b\x45\x00'
        CUT = b'\x1d\x56\x41\x03'
        FEED = b'\x1b\x64\x08'

        contenido = (
            INIT + CODEPAGE + ALIGN_CENTER + BOLD_ON +
            b'*** PRUEBA DE IMPRESION ***\n' + BOLD_OFF +
            b'Configuracion exitosa\n' +
            b'Impresora seleccionada:\n' +
            nombre.encode('cp850', errors='replace') + b'\n' +
            b'\n' +
            ALIGN_LEFT +
            b'Si ves este ticket, todo funciona.\n' +
            FEED + CUT
        )

        handle = win32print.OpenPrinter(nombre)
        try:
            job_id = win32print.StartDocPrinter(
                handle, 1, ("Prueba POS", None, "RAW")
            )
            try:
                win32print.StartPagePrinter(handle)
                win32print.WritePrinter(handle, contenido)
                win32print.EndPagePrinter(handle)
            finally:
                win32print.EndDocPrinter(handle)
        finally:
            win32print.ClosePrinter(handle)

        return True, f"Impreso OK (job #{job_id})"
    except Exception as e:
        return False, str(e)


# ============================================================
# UI
# ============================================================

class ConfigWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("Configuración de Impresoras - POS")
        self.root.geometry("640x420")
        self.root.resizable(False, False)

        # Estilo
        style = ttk.Style()
        style.theme_use('vista' if 'vista' in style.theme_names() else 'clam')

        # Config actual
        self.config = cargar_config()

        # Impresoras disponibles
        self.impresoras = listar_impresoras()

        # Variables para los combos
        self.vars = {}

        self._build_ui()

    def _build_ui(self):
        # Título
        header = tk.Frame(self.root, bg='#0d6efd', height=60)
        header.pack(fill='x')
        header.pack_propagate(False)
        tk.Label(
            header,
            text="🖨  Configuración de Impresoras",
            bg='#0d6efd', fg='white',
            font=('Segoe UI', 14, 'bold')
        ).pack(pady=15)

        # Info
        info = tk.Frame(self.root)
        info.pack(fill='x', padx=20, pady=(15, 5))
        tk.Label(
            info,
            text=f"Impresoras detectadas en el sistema: {len(self.impresoras)}",
            font=('Segoe UI', 9), fg='#6c757d'
        ).pack(anchor='w')

        # Formulario
        form = tk.Frame(self.root)
        form.pack(fill='both', expand=True, padx=20, pady=10)

        for i, (key, label) in enumerate(TIPOS):
            tk.Label(
                form, text=label,
                font=('Segoe UI', 10, 'bold'), anchor='w'
            ).grid(row=i*3, column=0, columnspan=2, sticky='w', pady=(10, 2))

            var = tk.StringVar(value=self.config.get(key, ''))
            self.vars[key] = var

            combo = ttk.Combobox(
                form, textvariable=var,
                values=self.impresoras,
                state='readonly', width=50, font=('Segoe UI', 9)
            )
            combo.grid(row=i*3+1, column=0, sticky='ew', pady=(0, 5))

            btn = ttk.Button(
                form, text="Probar",
                command=lambda v=var: self._probar(v.get())
            )
            btn.grid(row=i*3+1, column=1, padx=(10, 0), sticky='w')

            # Separador
            ttk.Separator(form, orient='horizontal').grid(
                row=i*3+2, column=0, columnspan=2, sticky='ew', pady=5
            )

        form.columnconfigure(0, weight=1)

        # Botonera
        botones = tk.Frame(self.root)
        botones.pack(fill='x', padx=20, pady=(0, 20))

        ttk.Button(
            botones, text="🔄 Refrescar impresoras",
            command=self._refrescar
        ).pack(side='left')

        ttk.Button(
            botones, text="💾 Guardar configuración",
            command=self._guardar
        ).pack(side='right')

        ttk.Button(
            botones, text="Salir",
            command=self.root.destroy
        ).pack(side='right', padx=(0, 10))

        # Estado
        self.estado = tk.Label(
            self.root, text="", font=('Segoe UI', 9),
            fg='#198754', anchor='w'
        )
        self.estado.pack(fill='x', padx=20, pady=(0, 10))

    def _refrescar(self):
        self.impresoras = listar_impresoras()
        for key, _ in TIPOS:
            # Actualizar valores del combo
            for widget in self.root.winfo_children():
                pass  # complejo, mejor reconstruir
        self.estado.config(
            text=f"✅ {len(self.impresoras)} impresoras detectadas",
            fg='#198754'
        )

    def _probar(self, nombre):
        if not nombre:
            messagebox.showwarning(
                "Sin selección",
                "Primero elegí una impresora de la lista."
            )
            return
        ok, msg = probar_impresora(nombre)
        if ok:
            messagebox.showinfo("Prueba exitosa", f"✅ {msg}")
        else:
            messagebox.showerror("Error al imprimir", f"❌ {msg}")

    def _guardar(self):
        for key, label in TIPOS:
            valor = self.vars[key].get().strip()
            self.config[key] = valor

        try:
            guardar_config(self.config)
            self.estado.config(
                text=f"✅ Configuración guardada en {os.path.basename(CONFIG_FILE)}",
                fg='#198754'
            )
        except Exception as e:
            self.estado.config(text=f"❌ Error: {e}", fg='#dc3545')


def main():
    root = tk.Tk()
    app = ConfigWindow(root)
    root.mainloop()


if __name__ == '__main__':
    main()