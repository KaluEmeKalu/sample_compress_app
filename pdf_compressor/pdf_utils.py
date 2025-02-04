from typing import List, Tuple
import io
from io import BytesIO
import logging
import fitz
import traceback
import sys
import os
from dotenv import load_dotenv
import asyncio
from functools import partial
import openai
from reportlab.lib.pagesizes import letter

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
    """Extract text from PDF with position information using PyMuPDF (fitz)"""
    try:
        sections: List[PDFSection] = []
        # Convert BytesIO to temporary file for fitz
        pdf_file.seek(0)
        pdf_data = pdf_file.read()
        doc = fitz.open("pdf", pdf_data)
        
        for page_num, page in enumerate(doc):
            # Get blocks which contain text and position information
            blocks = page.get_text("dict")["blocks"]
            
            for block in blocks:
                if "lines" in block:  # Only process text blocks
                    block_text = ""
                    min_x = float('inf')
                    min_y = float('inf')
                    max_x = float('-inf')
                    max_y = float('-inf')
                    
                    # Collect text and find bounding box for entire block
                    for line in block["lines"]:
                        for span in line["spans"]:
                            block_text += span["text"] + " "
                            bbox = span["bbox"]
                            min_x = min(min_x, bbox[0])
                            min_y = min(min_y, bbox[1])
                            max_x = max(max_x, bbox[2])
                            max_y = max(max_y, bbox[3])
                    
                    if block_text.strip():
                        position = (min_x, min_y, max_x, max_y)
                        sections.append(PDFSection(block_text.strip(), page_num, position))
        
        doc.close()
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

async def process_pdf_with_summaries(pdf_file: io.BytesIO) -> io.BytesIO:
    """Process PDF file and generate summaries with improved visual layout using PyMuPDF"""
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

        # Create new PDF using PyMuPDF
        pdf_file.seek(0)
        doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
        new_doc = fitz.open()
        
        # Process each page
        for i in range(len(doc)):
            # Create new page with letter size
            width, height = letter
            new_page = new_doc.new_page(width=width, height=height)
            
            # Copy original page content
            page = doc[i]
            target_rect = fitz.Rect(0, 0, width * 0.7, height)  # Leave space for sidebar
            new_page.show_pdf_page(target_rect, doc, i)
            
            # Get sections for this page
            page_sections = [(j, section) for j, section in enumerate(sections) if section.page == i and section.summary]
            
            if page_sections:
                # Add highlights and numbers for each section
                for j, section in page_sections:
                    # Create highlight
                    rect = fitz.Rect(section.position)
                    scaled_rect = fitz.Rect(
                        rect.x0 * 0.7, rect.y0,
                        rect.x1 * 0.7, rect.y1
                    )
                    new_page.draw_rect(scaled_rect, color=(1, 0.9, 0.2), fill=(1, 0.9, 0.2), fill_opacity=0.3)
                    
                    # Add section number in a circle
                    circle_x = scaled_rect.x1 + 5
                    circle_y = scaled_rect.y0
                    circle_radius = 8
                    new_page.draw_circle((circle_x + circle_radius, circle_y + circle_radius), circle_radius,
                                       color=(0.1, 0.3, 0.6), fill=(0.1, 0.3, 0.6))
                    new_page.insert_text((circle_x + circle_radius - 3, circle_y + circle_radius + 3),
                                       str(j), fontsize=8, color=(1, 1, 1))
                
                # Create sidebar
                sidebar_x = width * 0.75
                sidebar_y = 40
                sidebar_width = width * 0.2
                
                # Draw sidebar background
                sidebar_rect = fitz.Rect(sidebar_x - 10, 30, sidebar_x + sidebar_width, height - 30)
                new_page.draw_rect(sidebar_rect, color=(0.96, 0.96, 0.96), fill=(0.96, 0.96, 0.96))
                
                # Add summaries to sidebar
                for j, section in page_sections:
                    if not section.summary:
                        continue
                    
                    # Draw number box
                    box_rect = fitz.Rect(sidebar_x, sidebar_y, sidebar_x + 20, sidebar_y + 20)
                    new_page.draw_rect(box_rect, color=(0.1, 0.3, 0.6), fill=(0.1, 0.3, 0.6))
                    new_page.insert_text((sidebar_x + 7, sidebar_y + 14), str(j), fontsize=8, color=(1, 1, 1))
                    
                    # Add summary text
                    parts = section.summary.split('\n')
                    title = parts[0].replace('Title: ', '')
                    content = parts[1].replace('Summary: ', '') if len(parts) > 1 else section.summary
                    
                    # Add title
                    new_page.insert_text((sidebar_x + 25, sidebar_y + 14), title, fontsize=11)
                    sidebar_y += 20
                    
                    # Add content with word wrap
                    content_lines = [content[i:i+40] for i in range(0, len(content), 40)]
                    for line in content_lines:
                        new_page.insert_text((sidebar_x + 25, sidebar_y + 14), line, fontsize=10)
                        sidebar_y += 15
                    
                    sidebar_y += 20  # Space between summaries
        
        # Write to buffer
        output_buffer = io.BytesIO()
        output_buffer.write(new_doc.write())
        output_buffer.seek(0)
        
        return output_buffer
    except Exception as e:
        logger.error(f"Error processing PDF: {str(e)}")
        logger.error(f"Stack trace: {traceback.format_exc()}")
        raise Exception(f"Error processing PDF: {str(e)}")