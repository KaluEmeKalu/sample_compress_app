from io import BytesIO
import logging
from typing import Union, BinaryIO
from PyPDF2 import PdfReader, PdfWriter, errors
import traceback

logger = logging.getLogger(__name__)

def compress_pdf(pdf_file: Union[BytesIO, BinaryIO]) -> BytesIO:
    """
    Compress PDF file by reducing its quality
    
    Args:
        pdf_file: File object containing the PDF to compress. Can be either BytesIO or file object
        
    Returns:
        BytesIO: Buffer containing the compressed PDF
        
    Raises:
        Exception: If there's an error during compression
    """
    try:
        logger.info(f"Starting compression for file: {getattr(pdf_file, 'name', 'unknown')}")
        
        # Log initial file size
        pdf_file.seek(0, 2)  # Seek to end
        initial_size: int = pdf_file.tell()
        pdf_file.seek(0)  # Reset to beginning
        logger.info(f"Initial file size: {initial_size / 1024:.2f} KB")

        # Read the PDF file
        try:
            # Store file content in memory to avoid file pointer issues
            pdf_content: bytes = pdf_file.read()
            pdf_file_obj: BytesIO = BytesIO(pdf_content)
            pdf_reader: PdfReader = PdfReader(pdf_file_obj)
            logger.info(f"Successfully read PDF with {len(pdf_reader.pages)} pages")
        except errors.PdfReadError as e:
            logger.error(f"PDF Read Error: {str(e)}")
            logger.error(traceback.format_exc())
            raise Exception(f"Invalid or corrupted PDF file: {str(e)}")
        except Exception as e:
            logger.error(f"Error reading PDF: {str(e)}")
            logger.error(traceback.format_exc())
            raise Exception(f"Error reading PDF file: {str(e)}")

        pdf_writer: PdfWriter = PdfWriter()

        # Copy pages to writer with compression
        try:
            for i, page in enumerate(pdf_reader.pages):
                logger.debug(f"Processing page {i + 1}")
                # Add page with compression settings
                pdf_writer.add_page(page)
                # Apply compression to images if available
                if hasattr(page, '/Resources') and '/XObject' in page['/Resources']:
                    for obj in page['/Resources']['/XObject'].values():
                        if hasattr(obj, '/Filter'):
                            obj['/Filter'] = '/DCTDecode'  # JPEG compression
                            if hasattr(obj, '/DecodeParms'):
                                obj['/DecodeParms'] = None
            logger.info("Successfully copied all pages")
        except Exception as e:
            logger.error(f"Error processing PDF pages: {str(e)}")
            logger.error(traceback.format_exc())
            raise Exception(f"Error processing PDF pages: {str(e)}")

        # Create output buffer
        output_buffer: BytesIO = BytesIO()
        
        # Write to buffer with compression
        try:
            pdf_writer.write(output_buffer)
            logger.info("Successfully wrote compressed PDF to buffer")
        except Exception as e:
            logger.error(f"Error writing compressed PDF: {str(e)}")
            logger.error(traceback.format_exc())
            raise Exception(f"Error writing compressed PDF: {str(e)}")
        
        # Log final file size
        final_size: int = output_buffer.tell()
        logger.info(f"Final file size: {final_size / 1024:.2f} KB")
        logger.info(f"Compression ratio: {(1 - final_size/initial_size) * 100:.2f}%")
        
        # Get the compressed PDF
        output_buffer.seek(0)
        return output_buffer
    except Exception as e:
        logger.error(f"Unexpected error during PDF compression: {str(e)}")
        logger.error(traceback.format_exc())
        raise Exception(f"Error compressing PDF: {str(e)}")
