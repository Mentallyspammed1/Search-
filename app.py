import os
import argparse
import logging
from functools import lru_cache
from flask import Flask, render_template, request, jsonify, Blueprint
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from flask_compress import Compress
from flask_sslify import SSLify
from flask_mail import Mail, Message
from flask_socketio import SocketIO, emit
from flask_featureflags import FeatureFlag
from werkzeug.utils import secure_filename
import requests
from html import escape
from marshmallow import Schema, fields, ValidationError

# Initialize Flask app with basic configuration
app = Flask(__name__)
app.config['SECRET_KEY'] = 'mysecretkey'  # Hardcoded secret key
app.config['UPLOAD_FOLDER'] = 'uploads'  # Directory for file uploads
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limit request size to 16MB

# Define Blueprint for modular routing
main_bp = Blueprint('main', __name__)

# Hardcoded Google Custom Search API credentials for testing
API_KEY = 'AIzaSyBnMVWNJUwlah6vQSvqN-e6ZhOWS1ejgnI'  # Hardcoded API key
CX = '45f0f64b86de7475f'  # Hardcoded Custom Search Engine ID
BASE_URL = 'https://www.googleapis.com/customsearch/v1'  # API endpoint

# Hardcoded shutdown secret and HTTPS enforcement
SHUTDOWN_SECRET = 'mySecretShutdownKey123'  # Hardcoded shutdown key
ENFORCE_HTTPS = False  # HTTPS enforcement

# Configure logging for debugging and monitoring
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up rate limiting to prevent abuse
limiter = Limiter(get_remote_address, app=app, default_limits=["100 per day", "10 per minute"])

# Enable CORS for cross-origin requests
CORS(main_bp)

# Enforce HTTPS in production environments
if ENFORCE_HTTPS:
    SSLify(app)

# Compress responses to reduce bandwidth usage
Compress(app)

# Configure Gmail settings for email notifications
app.config['MAIL_SERVER'] = 'smtp.gmail.com'  # Gmail SMTP server
app.config['MAIL_PORT'] = 587  # Port for TLS
app.config['MAIL_USE_TLS'] = True  # Use TLS for security
app.config['MAIL_USERNAME'] = 'goodenuff94@gmail.com'  # Hardcoded Gmail address
app.config['MAIL_PASSWORD'] = 'Drums1@34'  # Hardcoded password
mail = Mail(app)

# Initialize SocketIO for real-time communication
socketio = SocketIO(app)

# Set up feature flags for toggling functionality
feature_flags = FeatureFlag(app)

# Store recent search history (in-memory, limited to 10 entries)
search_history = []

# Cache search results to reduce API calls (up to 100 entries)
@lru_cache(maxsize=100)
def cached_search(query, search_type, page, date_restrict, sort_order):
    params = {
        'key': API_KEY,
        'cx': CX,
        'q': query,
        'num': 10,  # Results per page
        'start': (page - 1) * 10 + 1  # Calculate offset
    }
    if search_type == 'image':
        params['searchType'] = 'image'
    if date_restrict:
        params['dateRestrict'] = date_restrict
    if sort_order:
        params['sort'] = sort_order
    response = requests.get(BASE_URL, params=params)
    return handle_api_response(response)

# Handle API response errors gracefully
def handle_api_response(response):
    if response.status_code == 200:
        return response.json()
    elif response.status_code == 403:
        logger.error("API request failed: Invalid API credentials (Status 403)")
        return {'error': 'Invalid API credentials'}, 403
    elif response.status_code == 429:
        logger.warning("API request failed: API quota exceeded (Status 429)")
        return {'error': 'API quota exceeded'}, 429
    elif response.status_code == 400:
        logger.error("API request failed: Bad Request (Status 400)")
        return {'error': 'Bad Request'}, 400
    else:
        logger.error(f"API request failed with status code: {response.status_code}")
        return {'error': f'API request failed with status {response.status_code}'}, response.status_code

# Validate and sanitize page parameter
def validate_page(page):
    try:
        page = int(page)
        return page if page >= 1 else 1
    except ValueError:
        return 1

# Add pagination links to API response
def add_pagination_links(data, query, search_type, page):
    if 'queries' in data:
        if 'nextPage' in data['queries']:
            data['next'] = f"/search?q={query}&search_type={search_type}&page={page + 1}"
        if 'previousPage' in data['queries']:
            data['previous'] = f"/search?q={query}&search_type={search_type}&page={page - 1}"
    return data

# Update search history with new queries
def add_to_history(query):
    if query not in search_history:
        search_history.append(query)
        if len(search_history) > 10:
            search_history.pop(0)  # Remove oldest entry

# Define schema for input validation
class SearchSchema(Schema):
    q = fields.Str(required=True)  # Query is mandatory
    search_type = fields.Str(load_default='web')  # Default to web search
    page = fields.Int(load_default=1)  # Default page is 1
    date_restrict = fields.Str()  # Optional date restriction
    sort = fields.Str()  # Optional sort order

# Define application routes
@main_bp.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')

@main_bp.route('/search', methods=['GET'])
@limiter.limit("10 per minute")  # Rate limit search requests
def search():
    """Handle search requests with validation and caching."""
    schema = SearchSchema()
    try:
        data = schema.load(request.args)
    except ValidationError as err:
        return jsonify(err.messages), 400

    query = escape(data['q'])  # Sanitize input
    search_type = data['search_type']
    page = validate_page(data['page'])
    date_restrict = data.get('date_restrict')
    sort_order = data.get('sort')

    if not query:
        return jsonify({'error': 'No query provided'}), 400

    api_data = cached_search(query, search_type, page, date_restrict, sort_order)
    if isinstance(api_data, tuple):  # Handle error responses
        return jsonify(api_data[0]), api_data[1]
    
    add_to_history(query)
    api_data = add_pagination_links(api_data, query, search_type, page)
    return jsonify(api_data)

@main_bp.route('/history', methods=['GET'])
def get_history():
    """Return the search history."""
    return jsonify(search_history)

@main_bp.route('/health', methods=['GET'])
def health():
    """Provide a health check endpoint."""
    return jsonify({'status': 'healthy'}), 200

@main_bp.route('/suggest', methods=['GET'])
def suggest():
    """Provide query suggestions (dummy implementation)."""
    query = escape(request.args.get('q', ''))
    suggestions = [query + ' suggestion1', query + ' suggestion2']
    return jsonify(suggestions)

@main_bp.route('/shutdown', methods=['POST'])
def shutdown():
    """Gracefully shut down the server with authorization."""
    secret = request.form.get('secret')
    if secret == SHUTDOWN_SECRET:
        logger.info("Server is commencing shutdown...")
        raise RuntimeError("Server shutdown")
    else:
        logger.warning("Shutdown attempt failed: Unauthorized access.")
        return 'Unauthorized', 403

@main_bp.route('/upload', methods=['POST'])
def upload_file():
    """Handle secure file uploads."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    filename = secure_filename(file.filename)  # Prevent directory traversal
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    return jsonify({'message': 'File uploaded successfully'}), 201

@main_bp.route('/notify', methods=['POST'])
def notify():
    """Send an email notification using Gmail."""
    msg = Message('Test Notification', sender='goodenuff94@gmail.com', recipients=['goodenuff94@gmail.com'])
    msg.body = 'This is a test email sent from your Flask app!'
    try:
        mail.send(msg)
        return jsonify({'message': 'Email sent successfully'}), 200
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        return jsonify({'error': 'Failed to send email'}), 500

# WebSocket event for real-time connection
@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connections."""
    emit('response', {'data': 'Connected'})

# Register the Blueprint with the app
app.register_blueprint(main_bp)

# Run the application with command-line arguments
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run the Flask app.')
    parser.add_argument('--port', type=int, default=5000, help='Port (default: 5000)')
    args = parser.parse_args()
    socketio.run(app, host='127.0.0.1', port=args.port, debug=True)