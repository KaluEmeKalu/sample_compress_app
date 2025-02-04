# Summit API - PDF Compression Service

A Django REST Framework service that compresses PDF files. This service is designed to be easily deployable on DigitalOcean App Platform with auto-scaling capabilities.

## Features

- PDF file compression endpoint
- Easy deployment to DigitalOcean App Platform
- Auto-scaling capabilities
- Health checks and monitoring
- Simple web interface for testing

## Local Development Setup

1. Create a virtual environment and install dependencies:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Run migrations:
```bash
python manage.py migrate
```

3. Start the development server:
```bash
python manage.py runserver
```

## Docker Local Development

1. Build and run using docker-compose:
```bash
docker-compose up --build
```

The API will be available at `http://localhost:8000`

## API Endpoints

### Compress PDF
- URL: `/api/compress/`
- Method: `POST`
- Content-Type: `multipart/form-data`
- Request Body:
  - `pdf_file`: PDF file to compress
- Response: Compressed PDF file

## Deployment to DigitalOcean App Platform

### Prerequisites
- DigitalOcean account
- GitHub repository with your code
- DigitalOcean CLI (doctl) installed (optional)

### Deployment Steps

1. Push your code to a GitHub repository

2. In the DigitalOcean Console:
   - Go to Apps -> Create App
   - Select your GitHub repository
   - Select the branch to deploy from
   - Choose the region closest to your users
   - Configure Environment Variables:
     - `DJANGO_SECRET_KEY`: Your secure secret key
     - `DJANGO_DEBUG`: "False"
     - `DJANGO_ALLOWED_HOSTS`: Will be automatically set by DigitalOcean

3. Deploy the app:
   - Click "Create Resources"
   - DigitalOcean will automatically build and deploy your application

### Alternative Deployment using doctl

1. Install and configure doctl:
```bash
brew install doctl  # For macOS
doctl auth init
```

2. Create the app:
```bash
doctl apps create --spec .do/app.yaml
```

3. Get your app info:
```bash
doctl apps list
```

## Auto-scaling Configuration

The app is configured to run on DigitalOcean App Platform with the following specifications:
- Instance Type: basic-xs (scalable)
- Initial Instance Count: 1
- Auto-scaling based on:
  - CPU utilization
  - Memory usage
  - Request count

You can adjust these settings in the DigitalOcean console under your app's Resources tab.

## Monitoring and Logs

Access monitoring and logs through the DigitalOcean App Platform dashboard:
1. Go to your app in the DigitalOcean console
2. Click on "Monitoring" to view metrics
3. Click on "Logs" to view application logs

## Security Notes

For production deployment:
1. Set a secure DJANGO_SECRET_KEY
2. Configure CORS settings if needed
3. Set up proper authentication if required
4. Enable SSL/TLS (automatically handled by DigitalOcean App Platform)

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request