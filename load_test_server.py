#!/usr/bin/env python3
"""
Flask test server for load testing the Romanian Legislative API Client.
Mimics the Streamlit app's /search endpoint for compatibility with existing locustfile.
"""

import os
import sys
import logging
from flask import Flask, request, jsonify

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from legislatie_client import LegislatieClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Initialize client with minimal logging to reduce noise during load tests
client = LegislatieClient()

@app.route('/search', methods=['POST'])
def search():
    """
    Handle search requests from load tests.
    Expects form data with parameters matching the Streamlit app.
    """
    try:
        # Parse form parameters (same as Streamlit app)
        numar_pagina = int(request.form.get('numar_pagina', 0))
        rezultate_pagina = int(request.form.get('rezultate_pagina', 10))
        an = request.form.get('an')
        numar = request.form.get('numar')
        text = request.form.get('text')
        titlu = request.form.get('titlu')
        
        # Convert empty strings to None
        an = an if an else None
        numar = numar if numar else None
        text = text if text else None
        titlu = titlu if titlu else None
        
        logger.debug(f"Search request: page={numar_pagina}, results_per_page={rezultate_pagina}, "
                     f"an={an}, numar={numar}, text={text[:50] if text else None}, titlu={titlu}")
        
        # Perform search
        results = client.search(
            numar_pagina=numar_pagina,
            rezultate_pagina=rezultate_pagina,
            an=an,
            numar=numar,
            text=text,
            titlu=titlu
        )
        
        # Return results as JSON
        return jsonify({
            'success': True,
            'results': results,
            'count': len(results) if results else 0
        })
        
    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint for load test verification."""
    try:
        health_status = client.check_health()
        return jsonify({
            'success': True,
            'health': health_status
        })
    except Exception as e:
        logger.error(f"Health check error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/', methods=['GET'])
def index():
    """Simple root endpoint to verify server is running."""
    return jsonify({
        'service': 'Romanian Legislative API Load Test Server',
        'version': '1.0',
        'endpoints': {
            '/search': 'POST - Perform legislative search',
            '/health': 'GET - System health check',
            '/': 'GET - This information'
        }
    })

if __name__ == '__main__':
    # Run on port 8501 to match locustfile expectations
    port = int(os.environ.get('PORT', 8501))
    host = os.environ.get('HOST', '0.0.0.0')
    
    logger.info(f"Starting load test server on {host}:{port}")
    logger.info("Server ready for load testing")
    
    app.run(host=host, port=port, debug=False, threaded=True)