from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import mysql.connector
from mysql.connector import Error
import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import secrets

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(32))

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', 'rootpassword'),
    'database': os.getenv('DB_NAME', 'subscription_tracker')
}

def get_db_connection():
    """Create and return a database connection"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

def init_db():
    """Initialize database and create tables"""
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor()
            
            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    email VARCHAR(100) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    is_admin BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Subscriptions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    cost DECIMAL(10, 2) NOT NULL,
                    billing_cycle ENUM('monthly', 'yearly', 'weekly') DEFAULT 'monthly',
                    renewal_date DATE NOT NULL,
                    category VARCHAR(50),
                    alternative_notes TEXT,
                    status ENUM('active', 'cancelled', 'paused') DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            
            # Admin settings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admin_settings (
                    id INT PRIMARY KEY DEFAULT 1,
                    ai_enabled BOOLEAN DEFAULT FALSE,
                    ai_provider ENUM('none', 'claude', 'openai', 'ollama') DEFAULT 'none',
                    api_key_encrypted TEXT,
                    feature_alternatives BOOLEAN DEFAULT FALSE,
                    feature_chat BOOLEAN DEFAULT FALSE,
                    feature_analysis BOOLEAN DEFAULT FALSE,
                    feature_recommendations BOOLEAN DEFAULT FALSE,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """)
            
            # Insert default admin settings
            cursor.execute("""
                INSERT IGNORE INTO admin_settings (id, ai_enabled, ai_provider) 
                VALUES (1, FALSE, 'none')
            """)
            
            connection.commit()
            cursor.close()
            connection.close()
            print("Database initialized successfully")
        except Error as e:
            print(f"Error initializing database: {e}")

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Admin decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT is_admin FROM users WHERE id = %s", (session['user_id'],))
            user = cursor.fetchone()
            cursor.close()
            connection.close()
            
            if not user or not user['is_admin']:
                return jsonify({'error': 'Admin access required'}), 403
        
        return f(*args, **kwargs)
    return decorated_function

# ============ AUTHENTICATION ROUTES ============

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        
        if not username or not email or not password:
            return jsonify({'error': 'All fields are required'}), 400
        
        password_hash = generate_password_hash(password)
        
        connection = get_db_connection()
        if connection:
            try:
                cursor = connection.cursor()
                cursor.execute(
                    "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
                    (username, email, password_hash)
                )
                connection.commit()
                cursor.close()
                connection.close()
                return jsonify({'message': 'User registered successfully'}), 201
            except Error as e:
                return jsonify({'error': 'Username or email already exists'}), 400
        
        return jsonify({'error': 'Database connection failed'}), 503
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            cursor.close()
            connection.close()
            
            if user and check_password_hash(user['password_hash'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['is_admin'] = user['is_admin']
                return jsonify({'message': 'Login successful', 'is_admin': user['is_admin']}), 200
            else:
                return jsonify({'error': 'Invalid credentials'}), 401
        
        return jsonify({'error': 'Database connection failed'}), 503
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ============ INITIAL SETUP ROUTE ============

@app.route('/setup', methods=['GET', 'POST'])
def initial_setup():
    """First-time setup - create admin user"""
    # Check if users already exist
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT COUNT(*) as user_count FROM users")
        result = cursor.fetchone()
        cursor.close()
        connection.close()
        
        # If users exist, redirect to login
        if result['user_count'] > 0:
            return redirect(url_for('login'))
    
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        
        if not username or not email or not password:
            return jsonify({'error': 'All fields are required'}), 400
        
        password_hash = generate_password_hash(password)
        
        connection = get_db_connection()
        if connection:
            try:
                cursor = connection.cursor()
                # Create first user as admin
                cursor.execute(
                    "INSERT INTO users (username, email, password_hash, is_admin) VALUES (%s, %s, %s, TRUE)",
                    (username, email, password_hash)
                )
                connection.commit()
                
                # Auto-login the new admin
                cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
                user = cursor.fetchone()
                
                cursor.close()
                connection.close()
                
                # Set session
                session['user_id'] = user[0]  # id
                session['username'] = user[1]  # username
                session['is_admin'] = True
                
                return jsonify({'message': 'Admin user created successfully', 'is_admin': True}), 201
            except Error as e:
                return jsonify({'error': str(e)}), 500
        
        return jsonify({'error': 'Database connection failed'}), 503
    
    return render_template('setup.html')

# ============ MAIN ROUTES ============

@app.route('/')
def index():
    """Redirect to setup if no users exist, otherwise to dashboard"""
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT COUNT(*) as user_count FROM users")
        result = cursor.fetchone()
        cursor.close()
        connection.close()
        
        # If no users exist, redirect to setup
        if result['user_count'] == 0:
            return redirect(url_for('initial_setup'))
    
    # If users exist, require login
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/health')
def health():
    """Health check endpoint"""
    connection = get_db_connection()
    if connection:
        connection.close()
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'timestamp': datetime.now().isoformat()
        }), 200
    else:
        return jsonify({
            'status': 'unhealthy',
            'database': 'disconnected',
            'timestamp': datetime.now().isoformat()
        }), 503

# ============ SUBSCRIPTION ROUTES ============

@app.route('/api/subscriptions', methods=['GET', 'POST'])
@login_required
def subscriptions():
    if request.method == 'POST':
        data = request.get_json()
        
        connection = get_db_connection()
        if connection:
            try:
                cursor = connection.cursor()
                cursor.execute("""
                    INSERT INTO subscriptions 
                    (user_id, name, cost, billing_cycle, renewal_date, category, alternative_notes, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    session['user_id'],
                    data.get('name'),
                    data.get('cost'),
                    data.get('billing_cycle', 'monthly'),
                    data.get('renewal_date'),
                    data.get('category'),
                    data.get('alternative_notes', ''),
                    data.get('status', 'active')
                ))
                connection.commit()
                cursor.close()
                connection.close()
                return jsonify({'message': 'Subscription added successfully'}), 201
            except Error as e:
                return jsonify({'error': str(e)}), 500
    
    elif request.method == 'GET':
        connection = get_db_connection()
        if connection:
            try:
                cursor = connection.cursor(dictionary=True)
                cursor.execute("""
                    SELECT * FROM subscriptions 
                    WHERE user_id = %s 
                    ORDER BY renewal_date ASC
                """, (session['user_id'],))
                subs = cursor.fetchall()
                cursor.close()
                connection.close()
                
                # Convert date objects to strings
                for sub in subs:
                    if sub['renewal_date']:
                        sub['renewal_date'] = sub['renewal_date'].isoformat()
                    if sub['created_at']:
                        sub['created_at'] = sub['created_at'].isoformat()
                
                return jsonify(subs), 200
            except Error as e:
                return jsonify({'error': str(e)}), 500

@app.route('/api/subscriptions/<int:sub_id>', methods=['PUT', 'DELETE'])
@login_required
def subscription_detail(sub_id):
    if request.method == 'PUT':
        data = request.get_json()
        connection = get_db_connection()
        if connection:
            try:
                cursor = connection.cursor()
                cursor.execute("""
                    UPDATE subscriptions 
                    SET name=%s, cost=%s, billing_cycle=%s, renewal_date=%s, 
                        category=%s, alternative_notes=%s, status=%s
                    WHERE id=%s AND user_id=%s
                """, (
                    data.get('name'),
                    data.get('cost'),
                    data.get('billing_cycle'),
                    data.get('renewal_date'),
                    data.get('category'),
                    data.get('alternative_notes'),
                    data.get('status'),
                    sub_id,
                    session['user_id']
                ))
                connection.commit()
                cursor.close()
                connection.close()
                return jsonify({'message': 'Subscription updated successfully'}), 200
            except Error as e:
                return jsonify({'error': str(e)}), 500
    
    elif request.method == 'DELETE':
        connection = get_db_connection()
        if connection:
            try:
                cursor = connection.cursor()
                cursor.execute("""
                    DELETE FROM subscriptions 
                    WHERE id=%s AND user_id=%s
                """, (sub_id, session['user_id']))
                connection.commit()
                cursor.close()
                connection.close()
                return jsonify({'message': 'Subscription deleted successfully'}), 200
            except Error as e:
                return jsonify({'error': str(e)}), 500

# ============ DASHBOARD API ============

@app.route('/api/dashboard')
@login_required
def get_dashboard_stats():
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Total subscriptions
            cursor.execute("""
                SELECT COUNT(*) as total_subscriptions 
                FROM subscriptions 
                WHERE user_id = %s AND status = 'active'
            """, (session['user_id'],))
            total = cursor.fetchone()
            
            # Monthly cost
            cursor.execute("""
                SELECT 
                    SUM(CASE 
                        WHEN billing_cycle = 'monthly' THEN cost
                        WHEN billing_cycle = 'yearly' THEN cost / 12
                        WHEN billing_cycle = 'weekly' THEN cost * 4.33
                    END) as monthly_cost
                FROM subscriptions 
                WHERE user_id = %s AND status = 'active'
            """, (session['user_id'],))
            monthly = cursor.fetchone()
            
            # Yearly cost
            cursor.execute("""
                SELECT 
                    SUM(CASE 
                        WHEN billing_cycle = 'monthly' THEN cost * 12
                        WHEN billing_cycle = 'yearly' THEN cost
                        WHEN billing_cycle = 'weekly' THEN cost * 52
                    END) as yearly_cost
                FROM subscriptions 
                WHERE user_id = %s AND status = 'active'
            """, (session['user_id'],))
            yearly = cursor.fetchone()
            
            # Spending by category
            cursor.execute("""
                SELECT 
                    category,
                    COUNT(*) as count,
                    SUM(CASE 
                        WHEN billing_cycle = 'monthly' THEN cost
                        WHEN billing_cycle = 'yearly' THEN cost / 12
                        WHEN billing_cycle = 'weekly' THEN cost * 4.33
                    END) as monthly_cost
                FROM subscriptions 
                WHERE user_id = %s AND status = 'active'
                GROUP BY category
            """, (session['user_id'],))
            categories = cursor.fetchall()
            
            # Upcoming renewals (next 7 days)
            cursor.execute("""
                SELECT * FROM subscriptions 
                WHERE user_id = %s 
                AND status = 'active'
                AND renewal_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 7 DAY)
                ORDER BY renewal_date ASC
            """, (session['user_id'],))
            renewals = cursor.fetchall()
            
            # Convert dates to strings
            for renewal in renewals:
                if renewal['renewal_date']:
                    renewal['renewal_date'] = renewal['renewal_date'].isoformat()
                if renewal['created_at']:
                    renewal['created_at'] = renewal['created_at'].isoformat()
            
            cursor.close()
            connection.close()
            
            return jsonify({
                'total_subscriptions': total['total_subscriptions'],
                'monthly_cost': float(monthly['monthly_cost'] or 0),
                'yearly_cost': float(yearly['yearly_cost'] or 0),
                'categories': categories,
                'upcoming_renewals': renewals
            }), 200
        except Error as e:
            return jsonify({'error': str(e)}), 500

# ============ ADMIN ROUTES ============

@app.route('/admin')
@admin_required
def admin_panel():
    return render_template('admin.html')

@app.route('/api/admin/settings', methods=['GET', 'PUT'])
@admin_required
def admin_settings():
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 503
    
    if request.method == 'GET':
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM admin_settings WHERE id = 1")
            settings = cursor.fetchone()
            cursor.close()
            connection.close()
            
            # Don't send the actual API key
            if settings and settings['api_key_encrypted']:
                settings['api_key_encrypted'] = '***REDACTED***'
            
            return jsonify(settings), 200
        except Error as e:
            return jsonify({'error': str(e)}), 500
    
    elif request.method == 'PUT':
        data = request.get_json()
        try:
            cursor = connection.cursor()
            cursor.execute("""
                UPDATE admin_settings 
                SET ai_enabled = %s, ai_provider = %s, api_key_encrypted = %s,
                    feature_alternatives = %s, feature_chat = %s, 
                    feature_analysis = %s, feature_recommendations = %s
                WHERE id = 1
            """, (
                data.get('ai_enabled', False),
                data.get('ai_provider', 'none'),
                data.get('api_key', None),  # In production, encrypt this
                data.get('feature_alternatives', False),
                data.get('feature_chat', False),
                data.get('feature_analysis', False),
                data.get('feature_recommendations', False)
            ))
            connection.commit()
            cursor.close()
            connection.close()
            return jsonify({'message': 'Settings updated successfully'}), 200
        except Error as e:
            return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=False)
