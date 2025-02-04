import io
import logging
from PyPDF2 import PdfReader, PdfWriter
import traceback

logger = logging.getLogger(__name__)

def compress_pdf(pdf_file):
    """
    Compress PDF file by reducing its quality
    
    Args:
        pdf_file: File object containing the PDF to compress
        
    Returns:
        BytesIO: Buffer containing the compressed PDF
        
    Raises:
        Exception: If there's an error during compression
    """
    try:
        logger.info(f"Starting compression for file: {getattr(pdf_file, 'name', 'unknown')}")
        
        # Log initial file size
        pdf_file.seek(0, 2)  # Seek to end
        initial_size = pdf_file.tell()
        pdf_file.seek(0)  # Reset to beginning
        logger.info(f"Initial file size: {initial_size / 1024:.2f} KB")

        # Read the PDF file
        try:
            pdf_reader = PdfReader(pdf_file)
            logger.info(f"Successfully read PDF with {len(pdf_reader.pages)} pages")
        except Exception as e:
            logger.error(f"Error reading PDF: {str(e)}")
            logger.error(traceback.format_exc())
            raise Exception(f"Error reading PDF file: {str(e)}")

        pdf_writer = PdfWriter()

        # Copy pages to writer with compression
        try:
            for i, page in enumerate(pdf_reader.pages):
                logger.debug(f"Processing page {i + 1}")
                pdf_writer.add_page(page)
            logger.info("Successfully copied all pages")
        except Exception as e:
            logger.error(f"Error processing PDF pages: {str(e)}")
            logger.error(traceback.format_exc())
            raise Exception(f"Error processing PDF pages: {str(e)}")

        # Create output buffer
        output_buffer = io.BytesIO()
        
        # Write to buffer with compression
        try:
            pdf_writer.write(output_buffer)
            logger.info("Successfully wrote compressed PDF to buffer")
        except Exception as e:
            logger.error(f"Error writing compressed PDF: {str(e)}")
            logger.error(traceback.format_exc())
            raise Exception(f"Error writing compressed PDF: {str(e)}")
        
        # Log final file size
        final_size = output_buffer.tell()
        logger.info(f"Final file size: {final_size / 1024:.2f} KB")
        logger.info(f"Compression ratio: {(1 - final_size/initial_size) * 100:.2f}%")
        
        # Get the compressed PDF
        output_buffer.seek(0)
        return output_buffer
    except Exception as e:
        logger.error(f"Unexpected error during PDF compression: {str(e)}")
        logger.error(traceback.format_exc())
        raise Exception(f"Error compressing PDF: {str(e)}")