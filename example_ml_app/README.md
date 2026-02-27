# Example ML Application - Sentiment Analysis API

A simple sentiment analysis API built with Flask to demonstrate the Automated Deployment Framework.

## Features

- 🎯 Simple keyword-based sentiment analysis
- 🚀 RESTful API with Flask
- 🐳 Docker-ready
- ✅ Health check endpoint

## API Endpoints

### GET /
Returns API information and available endpoints.

### GET /health
Health check endpoint for monitoring.

### POST /analyze
Analyze sentiment of input text.

**Request Body:**
```json
{
    "text": "This is a great product! I love it!"
}
```

**Response:**
```json
{
    "text": "This is a great product! I love it!",
    "sentiment": "positive",
    "score": 0.67,
    "positive_words": 2,
    "negative_words": 0
}
```

## Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
python app.py
```

3. Test the API:
```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "This is amazing!"}'
```

## Docker Deployment

1. Build the image:
```bash
docker build -t sentiment-api .
```

2. Run the container:
```bash
docker run -p 8000:8000 sentiment-api
```

## Automated Deployment

This application is designed to work with the Automated Deployment Framework. Simply provide the GitHub repository URL to deploy automatically to AWS EC2.
