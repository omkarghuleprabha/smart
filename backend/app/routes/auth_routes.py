from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from app.utils.db import get_db

auth_bp = Blueprint('auth_bp', __name__)

# Helper to map roles to table names
ROLE_MAP = {
    'district_admin': 'district_admins',
    'admin': 'taluka_admins',
    'worker': 'village_workers',
    'user': 'users'
}

# --- 🟢 REGISTRATION ROUTE ---
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')
        role = request.form.get('role', 'user')
        
        # Location IDs
        dist_id = request.form.get('district_id')
        tal_id = request.form.get('taluka_id')
        vil_id = request.form.get('village_id')

        if not name or not email or not password:
            flash("Name, Email, and Password are required!", "danger")
            return redirect(url_for('auth_bp.register'))

        table_name = ROLE_MAP.get(role, 'users')
        hashed_pw = generate_password_hash(password)
        
        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        try:
            # 🔴 DUPLICATE CHECK (Dynamic)
            check_query = f"SELECT id FROM {table_name} WHERE email=%s OR phone=%s"
            cursor.execute(check_query, (email, phone))
            if cursor.fetchone():
                flash(f"User with this Email or Mobile already exists in {role.replace('_', ' ').title()}.", "danger")
                return redirect(url_for('auth_bp.register'))

            # 🔹 INSERT LOGIC
            if role == 'district_admin':
                query = "INSERT INTO district_admins (name, email, phone, password, district_id) VALUES (%s, %s, %s, %s, %s)"
                cursor.execute(query, (name, email, phone, hashed_pw, dist_id))
            elif role == 'admin':
                query = "INSERT INTO taluka_admins (name, email, phone, password, taluka_id) VALUES (%s, %s, %s, %s, %s)"
                cursor.execute(query, (name, email, phone, hashed_pw, tal_id))
            elif role == 'worker':
                query = "INSERT INTO village_workers (name, email, phone, password, village_id) VALUES (%s, %s, %s, %s, %s)"
                cursor.execute(query, (name, email, phone, hashed_pw, vil_id))
            else:
                query = "INSERT INTO users (name, email, phone, password, role, village_id) VALUES (%s, %s, %s, %s, %s, %s)"
                cursor.execute(query, (name, email, phone, hashed_pw, 'user', vil_id))

            conn.commit()
            flash("Registration Successful! Please login.", "success")
            return redirect(url_for('auth_bp.login'))

        except Exception as e:
            conn.rollback()
            print(f"Database Error: {e}")
            flash("Registration failed due to a server error.", "danger")
        finally:
            conn.close()

    # GET Request: Fetch states for the dropdown
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name FROM states ORDER BY name ASC")
    states = cursor.fetchall()
    conn.close()
    return render_template('auth/register.html', states=states)


# --- 🔵 LOGIN ROUTE ---
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form.get('identifier')
        password = request.form.get('password')
        form_role = request.form.get('role') 

        table_name = ROLE_MAP.get(form_role, 'users')
        
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        try:
            # Using f-string for table name is okay here since it's mapped from a hardcoded dict
            query = f"SELECT * FROM {table_name} WHERE email = %s OR phone = %s"
            cursor.execute(query, (identifier, identifier))
            user = cursor.fetchone()

            if user and check_password_hash(user['password'], password):
                session.clear()
                session['user_id'] = user['id']
                session['user_name'] = user['name']
                session['role'] = form_role
                
                flash(f"Welcome back, {user['name']}!", "success")
                
                # Redirect Map
                redirect_map = {
                    'district_admin': 'auth_bp.district_dashboard',
                    'admin': 'auth_bp.taluka_dashboard',
                    'worker': 'auth_bp.worker_dashboard',
                    'user': 'auth_bp.citizen_dashboard'
                }
                return redirect(url_for(redirect_map.get(form_role, 'auth_bp.citizen_dashboard')))
            
            flash("Invalid credentials for the selected role.", "danger")
        except Exception as e:
            print(f"Login Error: {e}")
            flash("An error occurred during login.", "danger")
        finally:
            conn.close()
            
    return render_template('auth/login.html')

# --- 🔴 LOGOUT ROUTE ---
@auth_bp.route('/logout')
def logout():
    session.clear()
    flash("Successfully logged out.", "success")
    return redirect(url_for('auth_bp.login'))

# --- 🟡 DASHBOARD ROUTES (Unified Check) ---

@auth_bp.route('/citizen-dashboard')
def citizen_dashboard():
    if session.get('role') != 'user':
        return redirect(url_for('auth_bp.login'))
    
    user_id = session.get('user_id')
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Example: Fetching counts for the citizen
        # Adjust these queries based on what your "Smart Garbage Pro" stats actually are
        cursor.execute("SELECT COUNT(*) as total FROM complaints WHERE user_id = %s", (user_id,))
        stats = cursor.fetchone() 
        
        # If the query returns None or you need more specific keys:
        if not stats:
            stats = {'total': 0}
            
    except Exception as e:
        print(f"Error fetching stats: {e}")
        stats = {'total': 0}
    finally:
        conn.close()

    # Pass the 'stats' variable to the template
    return render_template('dashboard/citizen_dash.html', stats=stats)

@auth_bp.route('/district-dashboard')
def district_dashboard():
    if session.get('role') != 'district_admin':
        return redirect(url_for('auth_bp.login'))
    return render_template('dashboard/district_admin.html')

@auth_bp.route('/taluka-dashboard')
def taluka_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('auth_bp.login'))
    return render_template('dashboard/taluka_admin.html')

@auth_bp.route('/worker-dashboard')
def worker_dashboard():
    if session.get('role') != 'worker':
        return redirect(url_for('auth_bp.login'))
    return render_template('dashboard/worker_dash.html')

# --- 🟡 API ROUTES FOR DROPDOWNS ---

@auth_bp.route('/get_districts/<int:state_id>')
def get_districts(state_id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name FROM districts WHERE state_id = %s ORDER BY name ASC", (state_id,))
    data = cursor.fetchall()
    conn.close()
    return jsonify(data)

@auth_bp.route('/get_talukas/<int:district_id>')
def get_talukas(district_id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name FROM talukas WHERE district_id = %s ORDER BY name ASC", (district_id,))
    data = cursor.fetchall()
    conn.close()
    return jsonify(data)

@auth_bp.route('/get_villages/<int:taluka_id>')
def get_villages(taluka_id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name FROM villages WHERE taluka_id = %s ORDER BY name ASC", (taluka_id,))
    data = cursor.fetchall()
    conn.close()
    return jsonify(data)