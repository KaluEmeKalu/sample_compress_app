from rest_framework import serializers

class PDFFileSerializer(serializers.Serializer):
    pdf_file = serializers.FileField()
    
    def validate_pdf_file(self, value):
        if not value.name.endswith('.pdf'):
            raise serializers.ValidationError("Only PDF files are allowed")
        return value