#!/usr/bin/env python3
"""
Simple test server for load testing - returns dummy responses.
"""

from flask import Flask, request, jsonify
import time

app = Flask(__name__)

@app.route('/search', methods=['POST'])
def search():
    """Dummy search endpoint that simulates latency."""
    # Simulate processing time (50-200ms)
    time.sleep(0.05)
    
    # Return dummy results
    dummy_results = [
        {
            "Titlu": "LEGE nr. 123 din 2023",
            "Numar": "123",
            "DataVigoare": "2023-05-15T00:00:00",
            "Emitent": "PARLAMENTUL ROMÂNIEI",
            "Publicatie": "Monitorul Oficial nr. 456/2023",
            "Text": "Textul legii nr. 123 din 2023...",
            "TipAct": "LEGE",
            "LinkHtml": "https://legislatie.just.ro/Public/DetailiDocument/123456"
        }
    ]
    
    return jsonify({
        'success': True,
        'results': dummy_results,
        'count': 1
    })

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'success': True,
        'health': {
            'overall': 'healthy',
            'soap': 'healthy',
            'scraper': 'healthy',
            'cache': 'healthy'
        }
    })

if __name__ == '__main__':
    print("Starting dummy test server on port 8501...")
    app.run(host='0.0.0.0', port=8501, debug=False, threaded=True)