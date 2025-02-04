from typing import List, Dict, Any, Tuple
import io
import logging
from PyPDF2 import PdfReader
import openai
from django.conf import settings
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')

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

async def summarize_text(text: str) -> str:
    """
    Summarize text using OpenAI API
    
    Args:
        text: Text to summarize
        
    Returns:
        Summarized text
    """
    try:
        response = await openai.chat.completions.create(
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

async def process_pdf_with_summaries(pdf_file: io.BytesIO) -> List[PDFSection]:
    """
    Process PDF file and generate summaries for each section
    
    Args:
        pdf_file: BytesIO object containing the PDF
        
    Returns:
        List of PDFSection objects with summaries
    """
    try:
        sections = extract_text_with_positions(pdf_file)
        
        # Generate summaries for each section
        for section in sections:
            if len(section.text.split()) > 20:  # Only summarize sections with more than 20 words
                section.summary = await summarize_text(section.text)
            else:
                section.summary = section.text
        
        return sections
    except Exception as e:
        logger.error(f"Error processing PDF: {str(e)}")
        raise Exception(f"Error processing PDF: {str(e)}")