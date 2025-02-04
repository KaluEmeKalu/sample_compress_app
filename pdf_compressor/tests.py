from django.test import TestCase
from unittest.mock import MagicMock, patch
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from .pdf_utils import PDFSection, create_summary_sidebar

class PDFUtilsTests(TestCase):
    def setUp(self):
        # Create a sample PDFSection
        self.pdf_section = PDFSection(
            text="Sample text content",
            page=0,
            position=(10.0, 10.0, 100.0, 50.0)
        )
        self.pdf_section.summary = "Title: Sample Title\nSummary: This is a test summary."

    def test_create_summary_sidebar(self):
        """
        Test that create_summary_sidebar correctly handles PDFSection objects
        This test would have caught the 'not subscriptable' error
        """
        # Create a canvas for testing
        packet = BytesIO()
        c = canvas.Canvas(packet, pagesize=letter)
        page_height = letter[1]

        # Create a list of tuples (index, PDFSection) as expected by create_summary_sidebar
        summaries = [(0, self.pdf_section)]

        try:
            # This would have failed with TypeError if the function tried to access summary[1]
            # instead of using summary[1].summary
            create_summary_sidebar(c, summaries, page_height)
            c.save()
            success = True
        except TypeError:
            success = False

        self.assertTrue(success, "create_summary_sidebar should handle PDFSection objects correctly")

    def test_pdfsection_attributes(self):
        """
        Test PDFSection class attributes and initialization
        """
        section = PDFSection(
            text="Test content",
            page=1,
            position=(0.0, 0.0, 100.0, 50.0)
        )

        self.assertEqual(section.text, "Test content")
        self.assertEqual(section.page, 1)
        self.assertEqual(section.position, (0.0, 0.0, 100.0, 50.0))
        self.assertEqual(section.summary, "")  # Should start empty

    def test_summary_format(self):
        """
        Test that PDFSection summary formatting is correct
        """
        section = PDFSection(
            text="Test content",
            page=1,
            position=(0.0, 0.0, 100.0, 50.0)
        )
        
        # Set a properly formatted summary
        test_summary = "Title: Test\nSummary: This is a test summary."
        section.summary = test_summary

        # Verify the summary can be split as expected by create_summary_sidebar
        parts = section.summary.split('\n')
        self.assertEqual(len(parts), 2)
        self.assertTrue(parts[0].startswith("Title:"))
        self.assertTrue(parts[1].startswith("Summary:"))

    def test_create_summary_sidebar_with_empty_summary(self):
        """
        Test that create_summary_sidebar properly handles PDFSection objects with empty summaries
        """
        packet = BytesIO()
        c = canvas.Canvas(packet, pagesize=letter)
        page_height = letter[1]

        # Create a PDFSection with empty summary
        empty_section = PDFSection(
            text="Test content",
            page=1,
            position=(0.0, 0.0, 100.0, 50.0)
        )
        # Don't set summary, leaving it as empty string

        summaries = [(0, empty_section)]

        try:
            create_summary_sidebar(c, summaries, page_height)
            c.save()
            success = True
        except Exception as e:
            success = False

        self.assertTrue(success, "create_summary_sidebar should handle empty summaries gracefully")

    def test_create_summary_sidebar_with_multiple_sections(self):
        """
        Test that create_summary_sidebar can handle multiple PDFSection objects
        """
        packet = BytesIO()
        c = canvas.Canvas(packet, pagesize=letter)
        page_height = letter[1]

        # Create multiple PDFSection objects
        section1 = PDFSection(
            text="First section",
            page=1,
            position=(0.0, 0.0, 100.0, 50.0)
        )
        section1.summary = "Title: First\nSummary: First section summary."

        section2 = PDFSection(
            text="Second section",
            page=1,
            position=(0.0, 60.0, 100.0, 110.0)
        )
        section2.summary = "Title: Second\nSummary: Second section summary."

        summaries = [(0, section1), (1, section2)]

        try:
            create_summary_sidebar(c, summaries, page_height)
            c.save()
            success = True
        except Exception as e:
            success = False

        self.assertTrue(success, "create_summary_sidebar should handle multiple sections correctly")
