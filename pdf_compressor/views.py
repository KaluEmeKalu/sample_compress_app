from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import PDFFileSerializer
from .utils import compress_pdf
import magic

class PDFCompressorView(APIView):
    def post(self, request):
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
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
