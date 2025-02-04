from typing import List, Dict, Any, Tuple
import io
import logging
from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.generic import (
    FloatObject, ArrayObject, NumberObject, TextStringObject, 
    DictionaryObject, NameObject, createStringObject, IndirectObject,
    RectangleObject
)
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
    """
    try:
        client = openai.AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that creates concise summaries of text. Format your response as 'Title: [1-2 word title]\nSummary: [1-2 sentence summary]'"},
                {"role": "user", "content": f"Please summarize this text: {text}"}
            ],
            max_tokens=100
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Error summarizing text: {str(e)}")
        return "Error generating summary"

def create_highlight_annotation(writer: PdfWriter, page_num: int, rect: Tuple[float, float, float, float]) -> DictionaryObject:
    """Create a highlight annotation."""
    highlight = DictionaryObject()
    highlight.update({
        NameObject("/Type"): NameObject("/Annot"),
        NameObject("/Subtype"): NameObject("/Highlight"),
        NameObject("/F"): NumberObject(4),
        NameObject("/QuadPoints"): ArrayObject([
            FloatObject(rect[0]), FloatObject(rect[3]),
            FloatObject(rect[2]), FloatObject(rect[3]),
            FloatObject(rect[0]), FloatObject(rect[1]),
            FloatObject(rect[2]), FloatObject(rect[1])
        ]),
        NameObject("/Rect"): ArrayObject([
            FloatObject(rect[0]), FloatObject(rect[1]),
            FloatObject(rect[2]), FloatObject(rect[3])
        ]),
        NameObject("/C"): ArrayObject([
            FloatObject(1),  # Yellow highlight
            FloatObject(1),
            FloatObject(0)
        ]),
        NameObject("/CA"): NumberObject(0.3),  # Opacity
    })
    return highlight

def create_number_annotation(writer: PdfWriter, page_num: int, number: int, position: Tuple[float, float]) -> DictionaryObject:
    """Create a number annotation."""
    number_box = DictionaryObject()
    box_size = 15
    number_box.update({
        NameObject("/Type"): NameObject("/Annot"),
        NameObject("/Subtype"): NameObject("/Square"),
        NameObject("/F"): NumberObject(4),
        NameObject("/Rect"): ArrayObject([
            FloatObject(position[0]), FloatObject(position[1]),
            FloatObject(position[0] + box_size), FloatObject(position[1] + box_size)
        ]),
        NameObject("/C"): ArrayObject([
            FloatObject(0),  # Blue box
            FloatObject(0.5),
            FloatObject(1)
        ]),
        NameObject("/Contents"): createStringObject(str(number)),
        NameObject("/CA"): NumberObject(1),
        NameObject("/Border"): ArrayObject([0, 0, 1]),
        NameObject("/T"): createStringObject(f"Section {number}")
    })
    return number_box

def create_summary_annotation(writer: PdfWriter, page_num: int, number: int, summary: str, position: Tuple[float, float]) -> DictionaryObject:
    """Create a summary annotation in the left margin."""
    annotation = DictionaryObject()
    
    # Split summary into title and content
    parts = summary.split('\n')
    title = parts[0].replace('Title: ', '')
    content = parts[1].replace('Summary: ', '') if len(parts) > 1 else summary
    
    formatted_text = f"{number}. {title}\n\n{content}"
    
    annotation.update({
        NameObject("/Type"): NameObject("/Annot"),
        NameObject("/Subtype"): NameObject("/FreeText"),
        NameObject("/F"): NumberObject(4),
        NameObject("/Contents"): createStringObject(formatted_text),
        NameObject("/Rect"): ArrayObject([
            FloatObject(20),  # Left margin
            FloatObject(position[1]),
            FloatObject(180),  # Width of summary
            FloatObject(position[1] + 80)  # Height of summary
        ]),
        NameObject("/C"): ArrayObject([
            FloatObject(0),  # Black text
            FloatObject(0),
            FloatObject(0)
        ]),
        NameObject("/DA"): createStringObject("/Helv 10 Tf 0 0 0 rg"),  # Font settings
        NameObject("/Q"): NumberObject(0),  # Left-aligned
        NameObject("/Border"): ArrayObject([0, 0, 1]),
        NameObject("/BS"): DictionaryObject({
            NameObject("/Type"): NameObject("/Border"),
            NameObject("/W"): NumberObject(1),
            NameObject("/S"): NameObject("/S")
        })
    })
    return annotation

async def process_pdf_with_summaries(pdf_file: io.BytesIO) -> io.BytesIO:
    """
    Process PDF file and generate summaries with improved visual layout
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
        for i, section in enumerate(sections):
            if section.summary:
                if section.page not in page_annotations:
                    page_annotations[section.page] = []
                
                # Create highlight annotation
                highlight = create_highlight_annotation(writer, section.page, section.position)
                
                # Create number annotation
                number_pos = (section.position[2] + 5, section.position[3] - 15)  # Right of text, aligned with top
                number = create_number_annotation(writer, section.page, i, number_pos)
                
                # Create summary annotation
                summary_pos = (20, section.position[3])  # Left margin, aligned with text
                summary = create_summary_annotation(writer, section.page, i, section.summary, summary_pos)
                
                page_annotations[section.page].extend([highlight, number, summary])
        
        # Process each page
        for i in range(len(reader.pages)):
            page = reader.pages[i]
            writer.add_page(page)
            
            # Add annotations for this page
            if i in page_annotations:
                if "/Annots" in writer.pages[i]:
                    existing_annots = writer.pages[i]["/Annots"]
                    for annot in page_annotations[i]:
                        existing_annots.append(annot)
                else:
                    writer.pages[i][NameObject("/Annots")] = ArrayObject(page_annotations[i])
        
        # Write to buffer
        output_buffer = io.BytesIO()
        writer.write(output_buffer)
        output_buffer.seek(0)
        
        return output_buffer
    except Exception as e:
        logger.error(f"Error processing PDF: {str(e)}")
        logger.error(f"Stack trace: {traceback.format_exc()}")
        raise Exception(f"Error processing PDF: {str(e)}")