from django.db import models


class Categoria(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Categoría'
        verbose_name_plural = 'Categorías'

    def __str__(self):
        return self.nombre


class Proveedor(models.Model):
    nombre_o_razon_social = models.CharField(max_length=150)
    cuit = models.CharField(max_length=20, blank=True, null=True)
    telefono = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    direccion = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        verbose_name = 'Proveedor'
        verbose_name_plural = 'Proveedores'

    def __str__(self):
        return self.nombre_o_razon_social


class Producto(models.Model):
    codigo_barra = models.CharField(max_length=50, unique=True, blank=True, null=True)
    nombre = models.CharField(max_length=150)
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True, blank=True)
    precio_costo = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    precio_venta = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    alicuota_iva = models.DecimalField(max_digits=5, decimal_places=2, default=21.00)
    stock_actual = models.IntegerField(default=0)
    stock_minimo = models.IntegerField(default=5)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'

    def __str__(self):
        return f"{self.nombre} ({self.codigo_barra})"


class MovimientoStock(models.Model):
    TIPO_CHOICES = [
        ('ENTRADA', 'Entrada / Compra'),
        ('SALIDA', 'Salida / Venta'),
        ('AJUSTE', 'Ajuste de Inventario'),
    ]

    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='movimientos')

    # 🔽 NUEVO: Sucursal donde se hizo el movimiento
    sucursal = models.ForeignKey(
        'configuracion.Sucursal',
        on_delete=models.PROTECT,
        related_name='movimientos_stock',
        verbose_name="Sucursal",
        null=True, blank=True,
        help_text="Sucursal donde se registra este movimiento"
    )

    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    cantidad = models.IntegerField()
    fecha = models.DateTimeField(auto_now_add=True)
    motivo = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = 'Movimiento de Stock'
        verbose_name_plural = 'Movimientos de Stock'

    def __str__(self):
        return f"{self.tipo} - {self.producto.nombre} ({self.cantidad})"


# =========================================================
# LISTAS DE PRECIOS
# =========================================================

class ListaPrecio(models.Model):
    """Lista de precios (Central, Premium, Mayorista, etc.)"""
    nombre = models.CharField("Nombre", max_length=100)
    descripcion = models.CharField("Descripción", max_length=255, blank=True, null=True)
    activa = models.BooleanField("Activa", default=True)
    es_default = models.BooleanField(
        "Lista por Defecto", default=False,
        help_text="Se usa si la sucursal no tiene lista asignada"
    )
    orden = models.IntegerField("Orden", default=0, help_text="Para ordenar en listados")
    fecha_alta = models.DateTimeField("Fecha de Alta", auto_now_add=True, null=True)

    class Meta:
        verbose_name = "Lista de Precios"
        verbose_name_plural = "Listas de Precios"
        ordering = ['orden', 'nombre']

    def __str__(self):
        return self.nombre


class PrecioProducto(models.Model):
    """Precio de un producto en una lista específica."""
    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name='precios_lista'
    )
    lista_precio = models.ForeignKey(
        ListaPrecio,
        on_delete=models.CASCADE,
        related_name='precios_productos'
    )
    precio = models.DecimalField("Precio", max_digits=12, decimal_places=2)
    fecha_actualizacion = models.DateTimeField("Última Actualización", auto_now=True)

    class Meta:
        unique_together = ('producto', 'lista_precio')
        verbose_name = "Precio de Producto"
        verbose_name_plural = "Precios de Productos"
        ordering = ['producto__nombre', 'lista_precio__nombre']

    def __str__(self):
        return f"{self.producto.nombre} - {self.lista_precio.nombre}: ${self.precio}"


# =========================================================
# STOCK POR SUCURSAL
# =========================================================

class StockSucursal(models.Model):
    """Stock de un producto en una sucursal específica."""
    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name='stocks_sucursal'
    )
    sucursal = models.ForeignKey(
        'configuracion.Sucursal',
        on_delete=models.CASCADE,
        related_name='stocks'
    )
    cantidad = models.IntegerField("Cantidad", default=0)
    stock_minimo = models.IntegerField("Stock Mínimo", default=5)
    fecha_actualizacion = models.DateTimeField("Última Actualización", auto_now=True)

    class Meta:
        unique_together = ('producto', 'sucursal')
        verbose_name = "Stock por Sucursal"
        verbose_name_plural = "Stocks por Sucursal"
        ordering = ['producto__nombre', 'sucursal__nombre']

    def __str__(self):
        return f"{self.producto.nombre} - {self.sucursal.nombre}: {self.cantidad}"

    @property
    def necesita_reposicion(self):
        """True si el stock está por debajo del mínimo."""
        return self.cantidad <= self.stock_minimo