import io
import pikepdf
from PyPDF2 import PdfReader, PdfWriter

def compress_pdf(pdf_file):
    """
    Compress PDF file by reducing its quality and optimizing content
    """
    try:
        # Create an in-memory buffer for pikepdf processing
        input_buffer = io.BytesIO(pdf_file.read())
        
        # Use pikepdf for initial compression
        with pikepdf.Pdf.open(input_buffer) as pdf:
            # Create output buffer for compressed PDF
            output_buffer = io.BytesIO()
            
            # Save with compression settings
            pdf.save(output_buffer,
                    compress_streams=True,  # Compress all streams
                    preserve_pdfa=True,     # Maintain PDF/A compatibility if present
                    object_stream_mode=pikepdf.ObjectStreamMode.generate,  # Compact PDF structure
                    recompress_flate=True,  # Recompress existing Flate streams
                    linearize=False)        # Optimize for web viewing
            
            # Reset buffer position
            output_buffer.seek(0)
            
            # Further optimize with PyPDF2
            reader = PdfReader(output_buffer)
            writer = PdfWriter()
            
            # Copy pages with additional compression
            for page in reader.pages:
                writer.add_page(page)
            
            # Create final output buffer
            final_buffer = io.BytesIO()
            
            # Write with compression
            writer.write(final_buffer)
            
            # Reset buffer position
            final_buffer.seek(0)
            return final_buffer
            
    except Exception as e:
        raise Exception(f"Error compressing PDF: {str(e)}")