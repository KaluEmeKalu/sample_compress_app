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

def extract_text_with_positions(pdf_file: io.BytesIO) -> List[PDFSection]:
    """
    Extract text from PDF with position information
    
    Args:
        pdf_file: BytesIO object containing the PDF
        
    Returns:
        List of PDFSection objects containing text and position information
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
        
        return sections
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

async def process_pdf_with_summaries(pdf_file: io.BytesIO) -> io.BytesIO:
    """
    Process PDF file and generate summaries for each section
    
    Args:
        pdf_file: BytesIO object containing the PDF
        
    Returns:
        BytesIO object containing the annotated PDF
    """
    try:
        # Extract text and sections
        sections = await run_in_executor(extract_text_with_positions, pdf_file)
        
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
        
        # Create new PDF
        reader = PdfReader(pdf_file)
        writer = PdfWriter()
        
        # Dictionary to store annotations for each page
        page_annotations = {}
        
        # Group annotations by page
        for section in sections:
            if section.summary:
                if section.page not in page_annotations:
                    page_annotations[section.page] = []
                
                # Create annotation dictionary
                annotation = {
                    'contents': section.summary,
                    'rect': [50, section.position[1], 250, section.position[1] + 50],
                    'color': [1, 1, 0],  # Yellow
                    'title': f'Summary {datetime.now().strftime("%H:%M:%S")}'
                }
                page_annotations[section.page].append(annotation)
        
        # Process each page
        for i in range(len(reader.pages)):
            page = reader.pages[i]
            writer.add_page(page)
            
            # Add annotations for this page
            if i in page_annotations:
                annotations = []
                for annot in page_annotations[i]:
                    # Create annotation dictionary
                    annotation_dict = DictionaryObject()
                    annotation_dict.update({
                        NameObject("/Type"): NameObject("/Annot"),
                        NameObject("/Subtype"): NameObject("/Text"),
                        NameObject("/F"): NumberObject(4),
                        NameObject("/Contents"): createStringObject(annot['contents']),
                        NameObject("/Rect"): ArrayObject([
                            FloatObject(annot['rect'][0]),
                            FloatObject(annot['rect'][1]),
                            FloatObject(annot['rect'][2]),
                            FloatObject(annot['rect'][3])
                        ]),
                        NameObject("/C"): ArrayObject([
                            FloatObject(annot['color'][0]),
                            FloatObject(annot['color'][1]),
                            FloatObject(annot['color'][2])
                        ]),
                        NameObject("/T"): createStringObject(annot['title'])
                    })
                    annotations.append(annotation_dict)
                
                if annotations:
                    if "/Annots" in writer.pages[i]:
                        existing_annots = writer.pages[i]["/Annots"]
                        for annot in annotations:
                            existing_annots.append(annot)
                    else:
                        writer.pages[i][NameObject("/Annots")] = ArrayObject(annotations)
        
        # Write to buffer
        output_buffer = io.BytesIO()
        writer.write(output_buffer)
        output_buffer.seek(0)
        
        return output_buffer
    except Exception as e:
        logger.error(f"Error processing PDF: {str(e)}")
        logger.error(f"Stack trace: {traceback.format_exc()}")
        raise Exception(f"Error processing PDF: {str(e)}")