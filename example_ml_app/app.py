"""
Example ML Application - Simple Sentiment Analysis API
This is a sample application to test the Automated Deployment Framework
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import re

app = Flask(__name__)
CORS(app)

# Simple sentiment analysis (keyword-based)
POSITIVE_WORDS = {'good', 'great', 'excellent', 'amazing', 'wonderful', 'fantastic', 'love', 'best', 'awesome', 'happy'}
NEGATIVE_WORDS = {'bad', 'terrible', 'awful', 'horrible', 'worst', 'hate', 'poor', 'sad', 'disappointing', 'useless'}


def analyze_sentiment(text):
    """
    Simple sentiment analysis based on keyword matching.
    
    Args:
        text: Input text to analyze
        
    Returns:
        Dictionary with sentiment and score
    """
    # Convert to lowercase and split into words
    words = re.findall(r'\w+', text.lower())
    
    # Count positive and negative words
    positive_count = sum(1 for word in words if word in POSITIVE_WORDS)
    negative_count = sum(1 for word in words if word in NEGATIVE_WORDS)
    
    # Calculate sentiment
    if positive_count > negative_count:
        sentiment = 'positive'
        score = positive_count / (positive_count + negative_count + 1)
    elif negative_count > positive_count:
        sentiment = 'negative'
        score = negative_count / (positive_count + negative_count + 1)
    else:
        sentiment = 'neutral'
        score = 0.5
    
    return {
        'sentiment': sentiment,
        'score': round(score, 2),
        'positive_words': positive_count,
        'negative_words': negative_count
    }


@app.route('/')
def home():
    """Home endpoint with API information."""
    return jsonify({
        'service': 'Sentiment Analysis API',
        'version': '1.0.0',
        'status': 'running',
        'endpoints': {
            '/': 'API information',
            '/health': 'Health check',
            '/analyze': 'Analyze sentiment (POST)'
        }
    })


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'sentiment-analysis'
    })


@app.route('/analyze', methods=['POST'])
def analyze():
    """
    Analyze sentiment of input text.
    
    Request body:
    {
        "text": "Your text here"
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'text' not in data:
            return jsonify({
                'error': 'Missing "text" field in request body'
            }), 400
        
        text = data['text']
        
        if not text or len(text.strip()) == 0:
            return jsonify({
                'error': 'Text cannot be empty'
            }), 400
        
        # Perform sentiment analysis
        result = analyze_sentiment(text)
        result['text'] = text
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=False)
