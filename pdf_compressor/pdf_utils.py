from typing import List, Dict, Any, Tuple
import io
import logging
from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.generic import FloatObject, ArrayObject, NumberObject, TextStringObject, DictionaryObject, NameObject, createStringObject, IndirectObject
import openai
from django.conf import settings
import os
from dotenv import load_dotenv
import asyncio
from functools import partial
from datetime import datetime
import traceback
import sys

# Load environment variables
load_dotenv()

# Configure OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')

# Increase recursion limit for PyPDF2
sys.setrecursionlimit(10000)

logger = logging.getLogger(__name__)

class PDFSection:
    def __init__(self, text: str, page: int, position: Tuple[float, float, float, float]):
        self.text = text
        self.page = page
        self.position = position  # (x0, y0, x1, y1)
        self.summary: str = ""

def extract_text_with_positions(pdf_file: io.BytesIO) -> Tuple[List[PDFSection], PdfReader]:
    """
    Extract text from PDF with position information
    
    Args:
        pdf_file: BytesIO object containing the PDF
        
    Returns:
        Tuple of (List of PDFSection objects, PdfReader object)
    """
    try:
        sections: List[PDFSection] = []
        reader = PdfReader(pdf_file)
        
        for page_num, page in enumerate(reader.pages):
            # Extract text and layout
            text_with_positions = []
            def visitor_body(text: str, cm: Any, tm: Any, fontDict: Any, fontSize: Any) -> None:
                x = tm[4]
                y = tm[5]
                # Approximate text box dimensions based on font size
                height = fontSize if fontSize else 12
                width = sum(fontDict.get(ord(c), 1000) for c in text) * fontSize / 1000 if fontSize else len(text) * 12
                text_with_positions.append((text, (x, y, x + width, y + height)))
            
            page.extract_text(visitor_text=visitor_body)
            
            # Group text by paragraphs
            current_text = ""
            current_position = None
            
            for text, position in text_with_positions:
                if not current_position:
                    current_position = position
                
                # Check if text belongs to same paragraph (similar y-position)
                if current_position and abs(position[1] - current_position[1]) < 20:
                    current_text += " " + text
                    current_position = (
                        min(current_position[0], position[0]),
                        min(current_position[1], position[1]),
                        max(current_position[2], position[2]),
                        max(current_position[3], position[3])
                    )
                else:
                    if current_text:
                        sections.append(PDFSection(current_text.strip(), page_num, current_position))
                    current_text = text
                    current_position = position
            
            # Add last section
            if current_text:
                sections.append(PDFSection(current_text.strip(), page_num, current_position))
        
        return sections, reader
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {str(e)}")
        raise Exception(f"Error extracting text from PDF: {str(e)}")

def run_in_executor(func, *args):
    """Run a sync function in an executor."""
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, partial(func, *args))

async def summarize_text(text: str) -> str:
    """
    Summarize text using OpenAI API
    
    Args:
        text: Text to summarize
        
    Returns:
        Summarized text
    """
    try:
        client = openai.AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that creates concise summaries of text. Keep summaries to 1-2 sentences."},
                {"role": "user", "content": f"Please summarize this text: {text}"}
            ],
            max_tokens=100
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Error summarizing text: {str(e)}")
        return "Error generating summary"

def create_annotation_dict(writer: PdfWriter, page_num: int, text: str, rect: Tuple[float, float, float, float]) -> DictionaryObject:
    """Create a PDF annotation dictionary."""
    annotation = DictionaryObject()
    
    # Basic annotation properties
    annotation.update({
        NameObject("/Type"): NameObject("/Annot"),
        NameObject("/Subtype"): NameObject("/Text"),
        NameObject("/F"): NumberObject(4),
        NameObject("/Contents"): createStringObject(text),
        NameObject("/Rect"): ArrayObject([
            FloatObject(rect[0]),
            FloatObject(rect[1]),
            FloatObject(rect[0] + 200),
            FloatObject(rect[1] + 50)
        ]),
        NameObject("/P"): writer.pages[page_num].get_object(),
        NameObject("/T"): createStringObject(f"Summary {datetime.now().strftime('%H:%M:%S')}"),
        NameObject("/C"): ArrayObject([
            FloatObject(1),
            FloatObject(1),
            FloatObject(0)
        ]),
        NameObject("/CA"): NumberObject(1),
        NameObject("/Border"): ArrayObject([
            NumberObject(0),
            NumberObject(0),
            NumberObject(2)
        ]),
        NameObject("/M"): createStringObject(datetime.now().strftime("D:%Y%m%d%H%M%S"))
    })
    
    return annotation

async def process_pdf_with_summaries(pdf_file: io.BytesIO) -> io.BytesIO:
    """
    Process PDF file and generate summaries for each section
    
    Args:
        pdf_file: BytesIO object containing the PDF
        
    Returns:
        BytesIO object containing the annotated PDF
    """
    try:
        # Run synchronous PDF extraction in executor
        sections, reader = await run_in_executor(extract_text_with_positions, pdf_file)
        
        # Generate summaries for each section concurrently
        summary_tasks = []
        for section in sections:
            if len(section.text.split()) > 20:  # Only summarize sections with more than 20 words
                task = asyncio.create_task(summarize_text(section.text))
                summary_tasks.append((section, task))
            else:
                section.summary = section.text
        
        # Wait for all summaries to complete
        for section, task in summary_tasks:
            section.summary = await task
        
        # Create new PDF with annotations
        writer = PdfWriter()
        
        # Copy all pages from the original PDF
        for page in reader.pages:
            writer.add_page(page)
        
        # Add annotations for each section
        for section in sections:
            if section.summary:
                # Create annotation in the margin
                margin_x = 50  # Left margin position
                margin_y = section.position[1]  # Align with text vertically
                
                # Create and add annotation
                annotation = create_annotation_dict(
                    writer,
                    section.page,
                    section.summary,
                    (margin_x, margin_y, margin_x + 200, margin_y + 50)
                )
                
                # Get the page's annotations array, creating it if it doesn't exist
                page = writer.pages[section.page]
                if "/Annots" in page:
                    current_annots = page[NameObject("/Annots")]
                    if isinstance(current_annots, IndirectObject):
                        current_annots = current_annots.get_object()
                    current_annots.append(annotation)
                else:
                    page[NameObject("/Annots")] = ArrayObject([annotation])
        
        # Write the annotated PDF to a buffer
        output_buffer = io.BytesIO()
        writer.write(output_buffer)
        output_buffer.seek(0)
        
        return output_buffer
    except Exception as e:
        logger.error(f"Error processing PDF: {str(e)}")
        logger.error(f"Stack trace: {traceback.format_exc()}")
        raise Exception(f"Error processing PDF: {str(e)}")