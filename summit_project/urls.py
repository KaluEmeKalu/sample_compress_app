from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    # Serve the API documentation at both root and /api/
    path('', TemplateView.as_view(
        template_name='pdf_compressor/index.html',
        content_type='text/html'
    ), name='api-docs-root'),
    path('api/', include('pdf_compressor.urls')),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
