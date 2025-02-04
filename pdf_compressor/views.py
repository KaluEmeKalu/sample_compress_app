from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.renderers import TemplateHTMLRenderer, JSONRenderer
from rest_framework.request import Request
from django.http import HttpResponse
from .serializers import PDFFileSerializer
from .utils import compress_pdf
from .pdf_utils import process_pdf_with_summaries, PDFSection
import logging
import traceback
import io
from typing import Union, Optional, List
import json

logger = logging.getLogger(__name__)

def is_pdf(file_obj: Union[io.BytesIO, io.BufferedRandom]) -> bool:
    """
    Check if file is a PDF by checking its header bytes
    """
    try:
        # Read first 4 bytes
        pdf_header = file_obj.read(4)
        file_obj.seek(0)  # Reset file pointer
        # Check for PDF signature %PDF
        return pdf_header.startswith(b'%PDF')
    except Exception as e:
        logger.error(f"Error checking PDF header: {str(e)}")
        return False

class PDFCompressorView(APIView):
    """
    API endpoint that allows PDF files to be uploaded and compressed.
    """
    parser_classes = (MultiPartParser, FormParser)
    renderer_classes = [JSONRenderer, TemplateHTMLRenderer]
    template_name = 'pdf_compressor/index.html'
    
    def get(self, request: Request, *args, **kwargs) -> Response:
        """
        Renders the file upload form.
        """
        return Response({
            'serializer': PDFFileSerializer(),
            'title': 'PDF Compression API',
            'description': 'Upload a PDF file to compress it.'
        }, template_name=self.template_name)

    def render_form_with_error(self, error_message: str, status_code: int = 400) -> Response:
        """
        Helper method to render form with error message
        """
        context = {
            'serializer': PDFFileSerializer(),
            'title': 'PDF Compression API',
            'description': 'Upload a PDF file to compress it.',
            'error': error_message
        }
        return Response(context, status=status_code, template_name=self.template_name)

    def post(self, request: Request) -> Union[Response, HttpResponse]:
        """
        Handles PDF file upload and compression.
        """
        try:
            serializer = PDFFileSerializer(data=request.data)
            if not serializer.is_valid():
                logger.error(f"Serializer errors: {serializer.errors}")
                return self.render_form_with_error(
                    "Invalid form submission. Please try again."
                )

            if 'pdf_file' not in request.FILES:
                logger.error("No file was uploaded")
                return self.render_form_with_error(
                    "No file was uploaded. Please select a PDF file."
                )

            pdf_file = request.FILES['pdf_file']
            logger.info(f"Processing file: {pdf_file.name}")

            # Check file size
            if pdf_file.size > 10 * 1024 * 1024:  # 10MB limit
                logger.error("File too large")
                return self.render_form_with_error(
                    "File too large. Maximum size is 10MB."
                )

            # Validate file is a PDF
            if not pdf_file.name.lower().endswith('.pdf'):
                logger.error("File does not have .pdf extension")
                return self.render_form_with_error(
                    "Invalid file type. Only PDF files are allowed."
                )

            # Additional PDF validation
            if not is_pdf(pdf_file):
                logger.error("File is not a valid PDF (invalid header)")
                return self.render_form_with_error(
                    "Invalid PDF file format. Please ensure you're uploading a valid PDF."
                )
            
            try:
                # Store the file in memory to avoid file pointer issues
                file_content = pdf_file.read()
                pdf_file = io.BytesIO(file_content)
                pdf_file.name = request.FILES['pdf_file'].name
                
                compressed_pdf = compress_pdf(pdf_file)
                logger.info("PDF compression successful")
                
                # Return the PDF file directly as a download
                response = HttpResponse(
                    compressed_pdf.getvalue(),
                    content_type='application/pdf'
                )
                response['Content-Disposition'] = f'attachment; filename="compressed_{pdf_file.name}"'
                return response

            except Exception as e:
                logger.error(f"Error compressing PDF: {str(e)}")
                logger.error(traceback.format_exc())
                return self.render_form_with_error(
                    "Error compressing PDF. Please ensure the file is not corrupted.",
                    status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            logger.error(traceback.format_exc())
            return self.render_form_with_error(
                "An unexpected error occurred. Please try again.",
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class PDFSummarizerView(APIView):
    """
    API endpoint that allows PDF files to be uploaded and summarized.
    """
    parser_classes = (MultiPartParser, FormParser)
    renderer_classes = [JSONRenderer, TemplateHTMLRenderer]
    template_name = 'pdf_compressor/summarize.html'
    
    def get(self, request: Request, *args, **kwargs) -> Response:
        """
        Renders the file upload form for summarization.
        """
        return Response({
            'serializer': PDFFileSerializer(),
            'title': 'PDF Summarizer',
            'description': 'Upload a PDF file to generate summaries with margin annotations.'
        }, template_name=self.template_name)

    def render_form_with_error(self, error_message: str, status_code: int = 400) -> Response:
        """
        Helper method to render form with error message
        """
        context = {
            'serializer': PDFFileSerializer(),
            'title': 'PDF Summarizer',
            'description': 'Upload a PDF file to generate summaries with margin annotations.',
            'error': error_message
        }
        return Response(context, status=status_code, template_name=self.template_name)

    async def post(self, request: Request) -> Response:
        """
        Handles PDF file upload and summarization.
        """
        try:
            serializer = PDFFileSerializer(data=request.data)
            if not serializer.is_valid():
                logger.error(f"Serializer errors: {serializer.errors}")
                return self.render_form_with_error(
                    "Invalid form submission. Please try again."
                )

            if 'pdf_file' not in request.FILES:
                logger.error("No file was uploaded")
                return self.render_form_with_error(
                    "No file was uploaded. Please select a PDF file."
                )

            pdf_file = request.FILES['pdf_file']
            logger.info(f"Processing file for summarization: {pdf_file.name}")

            # Check file size
            if pdf_file.size > 10 * 1024 * 1024:  # 10MB limit
                logger.error("File too large")
                return self.render_form_with_error(
                    "File too large. Maximum size is 10MB."
                )

            # Validate file is a PDF
            if not pdf_file.name.lower().endswith('.pdf'):
                logger.error("File does not have .pdf extension")
                return self.render_form_with_error(
                    "Invalid file type. Only PDF files are allowed."
                )

            # Additional PDF validation
            if not is_pdf(pdf_file):
                logger.error("File is not a valid PDF (invalid header)")
                return self.render_form_with_error(
                    "Invalid PDF file format. Please ensure you're uploading a valid PDF."
                )
            
            try:
                # Store the file in memory to avoid file pointer issues
                file_content = pdf_file.read()
                pdf_file = io.BytesIO(file_content)
                pdf_file.name = request.FILES['pdf_file'].name
                
                # Process PDF and generate summaries
                sections = await process_pdf_with_summaries(pdf_file)
                logger.info("PDF summarization successful")
                
                # Return the summarized sections
                return Response({
                    'title': 'PDF Summary',
                    'filename': pdf_file.name,
                    'sections': [
                        {
                            'text': section.text,
                            'summary': section.summary,
                            'page': section.page + 1,  # 1-based page numbers
                            'position': section.position
                        }
                        for section in sections
                    ]
                }, template_name=self.template_name)

            except Exception as e:
                logger.error(f"Error summarizing PDF: {str(e)}")
                logger.error(traceback.format_exc())
                return self.render_form_with_error(
                    "Error summarizing PDF. Please ensure the file is not corrupted.",
                    status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            logger.error(traceback.format_exc())
            return self.render_form_with_error(
                "An unexpected error occurred. Please try again.",
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )
