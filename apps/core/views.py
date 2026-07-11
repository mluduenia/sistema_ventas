from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def dashboard(request):
    context = {
        'titulo': 'Dashboard',
    }
    return render(request, 'core/dashboard.html', context)

def index(request):
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    return render(request, 'core/index.html')