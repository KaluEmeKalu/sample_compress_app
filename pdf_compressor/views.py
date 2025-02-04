from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.renderers import TemplateHTMLRenderer, JSONRenderer
from .serializers import PDFFileSerializer
from .utils import compress_pdf
import magic
import logging
import sys
import traceback

logger = logging.getLogger(__name__)

class PDFCompressorView(APIView):
    """
    API endpoint that allows PDF files to be uploaded and compressed.
    """
    parser_classes = (MultiPartParser, FormParser)
    renderer_classes = [JSONRenderer, TemplateHTMLRenderer]
    template_name = 'pdf_compressor/index.html'
    
    def get(self, request, *args, **kwargs):
        """
        Renders the file upload form.
        """
        serializer = PDFFileSerializer()
        return Response({
            'serializer': serializer,
            'title': 'PDF Compression API',
            'description': 'Upload a PDF file to compress it.'
        }, template_name='pdf_compressor/index.html')

    def post(self, request):
        """
        Handles PDF file upload and compression.
        """
        try:
            serializer = PDFFileSerializer(data=request.data)
            if not serializer.is_valid():
                logger.error(f"Serializer errors: {serializer.errors}")
                return Response(
                    {'error': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST,
                    template_name='pdf_compressor/index.html'
                )

            if 'pdf_file' not in request.FILES:
                logger.error("No file was uploaded")
                return Response(
                    {'error': 'No file was uploaded'},
                    status=status.HTTP_400_BAD_REQUEST,
                    template_name='pdf_compressor/index.html'
                )

            pdf_file = request.FILES['pdf_file']
            logger.info(f"Processing file: {pdf_file.name}")

            try:
                # Try to read file type
                file_type = magic.from_buffer(pdf_file.read(1024), mime=True)
                pdf_file.seek(0)  # Reset file pointer
                logger.info(f"Detected file type: {file_type}")
            except Exception as e:
                logger.error(f"Error detecting file type: {str(e)}")
                logger.error(traceback.format_exc())
                # If magic fails, try to validate based on file extension
                if not pdf_file.name.lower().endswith('.pdf'):
                    return Response(
                        {'error': 'Invalid file type. Only PDF files are allowed.'},
                        status=status.HTTP_400_BAD_REQUEST,
                        template_name='pdf_compressor/index.html'
                    )
                file_type = 'application/pdf'  # Assume PDF based on extension

            if file_type != 'application/pdf':
                logger.error(f"Invalid file type detected: {file_type}")
                return Response(
                    {'error': 'Invalid file type. Only PDF files are allowed.'},
                    status=status.HTTP_400_BAD_REQUEST,
                    template_name='pdf_compressor/index.html'
                )
            
            try:
                compressed_pdf = compress_pdf(pdf_file)
                logger.info("PDF compression successful")
                response = Response(
                    compressed_pdf.getvalue(),
                    content_type='application/pdf',
                    status=status.HTTP_200_OK
                )
                response['Content-Disposition'] = f'attachment; filename="compressed_{pdf_file.name}"'
                return response
            except Exception as e:
                logger.error(f"Error compressing PDF: {str(e)}")
                logger.error(traceback.format_exc())
                return Response(
                    {'error': f'Error compressing PDF: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    template_name='pdf_compressor/index.html'
                )

        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            logger.error(traceback.format_exc())
            return Response(
                {'error': 'An unexpected error occurred'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                template_name='pdf_compressor/index.html'
            )
