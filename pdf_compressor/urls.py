from django.urls import path
from .views import PDFCompressorView, PDFSummarizerView

urlpatterns = [
    path('compress/', PDFCompressorView.as_view(), name='compress'),
    path('summarize/', PDFSummarizerView.as_view(), name='summarize'),
]