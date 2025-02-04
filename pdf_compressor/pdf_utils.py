from typing import List, Dict, Any, Tuple
import io
import logging
from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.generic import (
    FloatObject, ArrayObject, NumberObject, TextStringObject, 
    DictionaryObject, NameObject, createStringObject, IndirectObject,
    BooleanObject, NullObject
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
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO

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
    """Extract text from PDF with position information"""
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
    """Summarize text using OpenAI API"""
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

def create_summary_sidebar(c: canvas.Canvas, summaries: List[Tuple[int, PDFSection]], page_height: float):
    """Create a sidebar with numbered summaries"""
    # Constants for layout
    SIDEBAR_WIDTH = 140  # Narrower sidebar to match reference
    LEFT_MARGIN = 40  # Increased left margin
    RIGHT_MARGIN = 15
    TOP_MARGIN = 40  # Less top margin
    BOX_SIZE = 10  # Smaller number boxes
    BOX_MARGIN = 10  # More space before box
    LINE_HEIGHT = 14  # More line spacing
    SECTION_SPACING = 20  # More space between sections
    TITLE_SIZE = 11  # Slightly larger titles
    CONTENT_SIZE = 10  # Larger content
    CORNER_RADIUS = 8  # Rounded corners for sidebar
    
    # Draw light gray background with rounded corners for the sidebar
    c.setFillColorRGB(0.96, 0.96, 0.96)  # Very light gray
    # Save state to restore after clipping
    c.saveState()
    # Create rounded rectangle path
    p = c.beginPath()
    p.roundRect(LEFT_MARGIN, TOP_MARGIN, SIDEBAR_WIDTH, page_height - (TOP_MARGIN + LEFT_MARGIN), CORNER_RADIUS)
    c.clipPath(p)  # Clip to the rounded rectangle
    c.setFillColorRGB(0.96, 0.96, 0.96)
    c.rect(LEFT_MARGIN, TOP_MARGIN, SIDEBAR_WIDTH, page_height - (TOP_MARGIN + LEFT_MARGIN), fill=1)
    c.restoreState()
    
    # Start position for first summary
    y = page_height - (TOP_MARGIN + LINE_HEIGHT)
    
    for i, (_, section) in enumerate(summaries):
        if not section.summary:
            continue
            
        # Split summary into title and content
        parts = section.summary.split('\n')
        title = parts[0].replace('Title: ', '')
        content = parts[1].replace('Summary: ', '') if len(parts) > 1 else section.summary
        
        # Draw small square box with number
        c.setFillColorRGB(0.1, 0.3, 0.6)  # Darker blue color from reference
        box_x = LEFT_MARGIN + BOX_MARGIN
        box_y = y - BOX_SIZE
        # Save state for rounded box
        c.saveState()
        p = c.beginPath()
        p.roundRect(box_x, box_y, BOX_SIZE, BOX_SIZE, 2)  # Slightly rounded corners
        c.clipPath(p)
        c.rect(box_x, box_y, BOX_SIZE, BOX_SIZE, fill=1)
        c.restoreState()
        
        # Draw number
        c.setFillColorRGB(1, 1, 1)  # White text
        c.setFont("Times-Bold", 8)  # Slightly larger font for better visibility
        number = str(i + 1)
        number_width = c.stringWidth(number, "Times-Bold", 8)
        number_x = box_x + (BOX_SIZE - number_width) / 2
        number_y = box_y + 2.5  # Better vertical centering
        c.drawString(number_x, number_y, number)
        
        # Calculate text position
        text_x = LEFT_MARGIN + BOX_MARGIN + BOX_SIZE + 8  # Text starts after box
        
        # Draw title with proper alignment
        c.setFillColorRGB(0.2, 0.2, 0.2)  # Dark gray for better readability
        c.setFont("Times-Bold", TITLE_SIZE)  # Bold Times for titles
        
        # Word wrap title
        wrapped_title = []
        current_line = ""
        max_width = SIDEBAR_WIDTH - (text_x - LEFT_MARGIN + 5)  # Slightly narrower for text
        
        for word in title.split():
            test_line = current_line + (" " if current_line else "") + word
            if c.stringWidth(test_line, "Helvetica-Bold", TITLE_SIZE) <= max_width:
                current_line = test_line
            else:
                if current_line:
                    wrapped_title.append(current_line)
                current_line = word
        if current_line:
            wrapped_title.append(current_line)
        
        # Draw wrapped title
        for line in wrapped_title:
            c.drawString(text_x, y, line)
            y -= LINE_HEIGHT
        
        # Add spacing between title and content
        y -= LINE_HEIGHT / 2
        
        # Draw content with proper styling
        c.setFillColorRGB(0.4, 0.4, 0.4)  # Lighter gray for content
        c.setFont("Times-Roman", CONTENT_SIZE)  # Use Times-Roman for a lighter look
        
        # Add proper spacing between title and content
        y -= LINE_HEIGHT * 1.2  # Slightly more space for better readability
        
        # Word wrap content with proper alignment
        wrapped_content = []
        current_line = ""
        max_width = SIDEBAR_WIDTH - (text_x - LEFT_MARGIN + 5)  # Match title width
        
        for word in content.split():
            test_line = current_line + (" " if current_line else "") + word
            if c.stringWidth(test_line, "Helvetica", CONTENT_SIZE) <= max_width:
                current_line = test_line
            else:
                if current_line:
                    wrapped_content.append(current_line)
                current_line = word
        if current_line:
            wrapped_content.append(current_line)
        
        # Draw wrapped content with minimal spacing
        for line in wrapped_content:
            c.drawString(text_x, y, line)  # Use same text_x for consistent alignment
            y -= LINE_HEIGHT  # Use defined line height
        
        # Add space between sections
        y -= SECTION_SPACING  # Use defined section spacing

def create_highlight_annotation(writer: PdfWriter, page_num: int, rect: Tuple[float, float, float, float]) -> DictionaryObject:
    """Create a highlight annotation"""
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
            FloatObject(0.9),
            FloatObject(0.2)
        ]),
        NameObject("/CA"): NumberObject(0.3),  # Opacity
        NameObject("/AP"): DictionaryObject({
            NameObject("/N"): NullObject()
        })
    })
    return highlight

def create_number_annotation(writer: PdfWriter, page_num: int, number: int, position: Tuple[float, float]) -> DictionaryObject:
    """Create a number annotation"""
    number_box = DictionaryObject()
    box_size = 16.0
    number_box.update({
        NameObject("/Type"): NameObject("/Annot"),
        NameObject("/Subtype"): NameObject("/Square"),
        NameObject("/F"): NumberObject(4),
        NameObject("/Rect"): ArrayObject([
            FloatObject(position[0]),
            FloatObject(position[1]),
            FloatObject(position[0] + box_size),
            FloatObject(position[1] + box_size)
        ]),
        NameObject("/C"): ArrayObject([
            FloatObject(0.2),  # Blue box
            FloatObject(0.4),
            FloatObject(0.8)
        ]),
        NameObject("/Contents"): createStringObject(str(number)),
        NameObject("/CA"): NumberObject(1),
        NameObject("/Border"): ArrayObject([
            NumberObject(0),
            NumberObject(0),
            NumberObject(1)
        ]),
        NameObject("/AP"): DictionaryObject({
            NameObject("/N"): NullObject()
        })
    })
    return number_box

async def process_pdf_with_summaries(pdf_file: io.BytesIO) -> io.BytesIO:
    """Process PDF file and generate summaries with improved visual layout"""
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
        
        # Process each page
        for i in range(len(reader.pages)):
            page = reader.pages[i]
            writer.add_page(page)
            
            # Get sections for this page and create annotations
            annotations = []
            page_sections = []
            
            # Process sections for this page
            for j, section in enumerate(sections):
                if section.page == i and section.summary:
                    page_sections.append((j, section))
                # Create highlight annotation
                highlight = create_highlight_annotation(writer, i, section.position)
                annotations.append(highlight)
                
                # Create number annotation
                number_pos = (section.position[2] + 5, section.position[3] - 15)
                number = create_number_annotation(writer, i, j, number_pos)
                annotations.append(number)
            
            # Add annotations to page
            if annotations:
                if "/Annots" in writer.pages[i]:
                    existing_annots = writer.pages[i]["/Annots"]
                    if isinstance(existing_annots, IndirectObject):
                        existing_annots = existing_annots.get_object()
                    for annot in annotations:
                        existing_annots.append(annot)
                else:
                    writer.pages[i][NameObject("/Annots")] = ArrayObject(annotations)
            
            # Create sidebar with summaries
            if page_sections:
                # Create a new page with summaries
                packet = BytesIO()
                c = canvas.Canvas(packet, pagesize=letter)
                create_summary_sidebar(c, page_sections, letter[1])
                c.save()
                
                # Merge sidebar with main page (sidebar first, then content)
                packet.seek(0)
                sidebar = PdfReader(packet)
                sidebar_page = sidebar.pages[0]
                # Create a new page with sidebar first
                new_page = writer.pages[i]
                new_page.merge_page(sidebar_page)
        
        # Write to buffer
        output_buffer = io.BytesIO()
        writer.write(output_buffer)
        output_buffer.seek(0)
        
        return output_buffer
    except Exception as e:
        logger.error(f"Error processing PDF: {str(e)}")
        logger.error(f"Stack trace: {traceback.format_exc()}")
        raise Exception(f"Error processing PDF: {str(e)}")