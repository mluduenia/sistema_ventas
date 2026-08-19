from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Producto, Categoria, Proveedor
from .forms import ProductoForm, CategoriaForm, ProveedorForm

# ==========================================
# --- PRODUCTOS ---
# ==========================================

@login_required
def lista_productos(request):
    """Listado de productos con filtros de búsqueda, rubro y proveedor."""
    productos = Producto.objects.select_related('categoria', 'proveedor').all()

    q = request.GET.get('q')
    if q:
        productos = productos.filter(nombre__icontains=q) | productos.filter(codigo_barra__icontains=q)

    cat_id = request.GET.get('categoria')
    if cat_id:
        productos = productos.filter(categoria_id=cat_id)

    prov_id = request.GET.get('proveedor')
    if prov_id:
        productos = productos.filter(proveedor_id=prov_id)

    categorias = Categoria.objects.all()
    proveedores = Proveedor.objects.all()

    context = {
        'productos': productos,
        'categorias': categorias,
        'proveedores': proveedores,
    }
    return render(request, 'productos/lista_productos.html', context)


@login_required
def crear_producto(request):
    """Creación de un producto con depuración de errores."""
    if request.method == 'POST':
        form = ProductoForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, '¡Producto registrado correctamente!')
            return redirect('productos:lista_productos')
        else:
            # Imprime la causa exacta en la terminal de VS Code si falla
            print("=== ERROR AL CREAR PRODUCTO ===")
            print(form.errors)
            messages.error(request, 'No se pudo guardar el producto. Revisa los errores marcados.')
    else:
        form = ProductoForm()

    return render(request, 'productos/form_producto.html', {
        'form': form,
        'titulo': 'Nuevo Producto'
    })


@login_required
def editar_producto(request, pk):
    """Edición de un producto existente."""
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == 'POST':
        form = ProductoForm(request.POST, request.FILES, instance=producto)
        if form.is_valid():
            form.save()
            messages.success(request, '¡Producto actualizado correctamente!')
            return redirect('productos:lista_productos')
        else:
            print("=== ERROR AL EDITAR PRODUCTO ===")
            print(form.errors)
            messages.error(request, 'No se pudieron guardar los cambios. Revisa los errores.')
    else:
        form = ProductoForm(instance=producto)

    return render(request, 'productos/form_producto.html', {
        'form': form,
        'producto': producto,
        'titulo': 'Editar Producto'
    })


@login_required
def eliminar_producto(request, pk):
    """Eliminación de un producto."""
    producto = get_object_or_404(Producto, pk=pk)
    producto.delete()
    messages.success(request, 'Producto eliminado con éxito.')
    return redirect('productos:lista_productos')


# ==========================================
# --- CATEGORÍAS ---
# ==========================================

@login_required
def lista_categorias(request):
    """Listado de categorías/rubros."""
    categorias = Categoria.objects.all()
    return render(request, 'productos/lista_categorias.html', {'categorias': categorias})


@login_required
def crear_categoria(request):
    """Creación de una categoría/rubro."""
    if request.method == 'POST':
        form = CategoriaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Categoría registrada con éxito.')
            next_url = request.GET.get('next')
            return redirect(next_url if next_url else 'productos:lista_categorias')
        else:
            messages.error(request, 'Error al guardar la categoría.')
    else:
        form = CategoriaForm()
    return render(request, 'productos/form_categoria.html', {'form': form})


# ==========================================
# --- PROVEEDORES ---
# ==========================================

@login_required
def lista_proveedores(request):
    """Listado de proveedores."""
    proveedores = Proveedor.objects.all()
    return render(request, 'productos/lista_proveedores.html', {'proveedores': proveedores})


@login_required
def crear_proveedor(request):
    """Creación de un proveedor."""
    if request.method == 'POST':
        form = ProveedorForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Proveedor registrado con éxito.')
            next_url = request.GET.get('next')
            return redirect(next_url if next_url else 'productos:lista_proveedores')
        else:
            messages.error(request, 'Error al guardar el proveedor.')
    else:
        form = ProveedorForm()
    return render(request, 'productos/form_proveedor.html', {'form': form})