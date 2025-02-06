# Summit PDF API

A Django-based API for PDF processing and summarization.

## Features

- PDF compression
- Text extraction
- Document summarization
- Highlight generation

## Deployment

This application is configured for deployment on DigitalOcean App Platform.

### Required Environment Variables

- DJANGO_SECRET_KEY
- OPENAI_API_KEY
- SPACES_ACCESS_KEY
- SPACES_SECRET_KEY

### Auto-scaling Configuration

- Minimum: 2 instances
- Maximum: 10 instances
- Scales based on:
  - CPU usage > 70%
  - Memory usage > 80%

### Database

Uses PostgreSQL managed by DigitalOcean with automatic configuration via DATABASE_URL.

### Caching

Redis is used for:
- Session storage
- Cache backend
- Task queue broker