from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.renderers import TemplateHTMLRenderer, JSONRenderer
from .serializers import PDFFileSerializer
from .utils import compress_pdf
import magic

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
        
        Parameters:
        - pdf_file: The PDF file to compress (required)
        
        Returns:
        - Compressed PDF file as attachment
        """
        serializer = PDFFileSerializer(data=request.data)
        if serializer.is_valid():
            pdf_file = request.FILES['pdf_file']
            
            # Verify file is actually a PDF
            file_type = magic.from_buffer(pdf_file.read(1024), mime=True)
            pdf_file.seek(0)  # Reset file pointer
            
            if file_type != 'application/pdf':
                return Response(
                    {"error": "Invalid file type. Only PDF files are allowed."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                compressed_pdf = compress_pdf(pdf_file)
                response = Response(
                    compressed_pdf.getvalue(),
                    content_type='application/pdf',
                    status=status.HTTP_200_OK
                )
                response['Content-Disposition'] = f'attachment; filename="compressed_{pdf_file.name}"'
                return response
            except Exception as e:
                return Response(
                    {"error": str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
            template_name='pdf_compressor/index.html'
        )
