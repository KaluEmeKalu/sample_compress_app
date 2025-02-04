from django.urls import path
from django.views.generic import TemplateView
from .views import PDFCompressorView

urlpatterns = [
    path('compress/', PDFCompressorView.as_view(), name='compress-pdf'),
    path('', TemplateView.as_view(
        template_name='pdf_compressor/index.html',
        content_type='text/html'
    ), name='api-docs'),
]