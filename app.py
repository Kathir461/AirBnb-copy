"""Airbnb-inspired student project: Flask, Jinja HTML/CSS and MySQL."""
import os
import re
import secrets
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

import click
import pymysql
from dotenv import load_dotenv
from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()
CATEGORIES = [('All homes', 'home'), ('Amazing pools', 'pool'), ('Countryside', 'leaf'), ('Cabins', 'cabin'), ('Design', 'design')]

def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(SECRET_KEY=os.getenv('SECRET_KEY'), SESSION_COOKIE_HTTPONLY=True,
                      SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE', '0') == '1',
                      PERMANENT_SESSION_LIFETIME=timedelta(hours=12), MAX_CONTENT_LENGTH=16384)
    if test_config:
        app.config.update(test_config)
    if not app.config['SECRET_KEY'] or len(app.config['SECRET_KEY']) < 32:
        raise RuntimeError('Set SECRET_KEY to a random string of at least 32 characters. See README.md.')

    def db():
        if 'db' not in g:
            options = dict(host=os.getenv('MYSQL_HOST', '127.0.0.1'), port=int(os.getenv('MYSQL_PORT', '3306')),
                           user=os.getenv('MYSQL_USER', 'root'), password=os.getenv('MYSQL_PASSWORD', ''),
                           database=os.getenv('MYSQL_DATABASE', 'stayclub'), charset='utf8mb4',
                           cursorclass=pymysql.cursors.DictCursor, autocommit=False, connect_timeout=10)
            if os.getenv('MYSQL_SSL_CA'):
                options['ssl'] = {'ca': os.environ['MYSQL_SSL_CA'], 'check_hostname': True}
            g.db = pymysql.connect(**options)
        return g.db

    def query(sql, args=(), one=False):
        with db().cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchone() if one else cur.fetchall()

    @app.teardown_appcontext
    def close_db(error=None):
        connection = g.pop('db', None)
        if connection:
            connection.close()

    @app.before_request
    def protect_and_load_user():
        g.user = None
        if request.endpoint == 'static':
            return
        session.setdefault('csrf', secrets.token_urlsafe(32))
        if request.method == 'POST':
            if not secrets.compare_digest(session['csrf'].encode(), request.form.get('csrf_token', '').encode()):
                abort(400, 'Your form expired. Reload the page and try again.')
        if session.get('user_id'):
            g.user = query('SELECT id, name, email FROM users WHERE id=%s', (session['user_id'],), one=True)
            if not g.user:
                session.pop('user_id', None)

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self'; style-src 'self'; script-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
        if request.endpoint != 'static':
            response.headers['Cache-Control'] = 'no-store'
        return response

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not g.user:
                flash('Log in to manage your stays and bookings.', 'info')
                return redirect(url_for('login'))
            return view(*args, **kwargs)
        return wrapped

    @app.context_processor
    def shared():
        return {'categories': CATEGORIES}

    @app.get('/')
    def home():
        destination = request.args.get('destination', '').strip()[:100]
        category = request.args.get('category', 'All homes')
        if category not in dict(CATEGORIES):
            category = 'All homes'
        sql = 'SELECT * FROM stays WHERE (location LIKE %s OR title LIKE %s)'
        params = ['%' + destination + '%', '%' + destination + '%']
        if category != 'All homes':
            sql += ' AND category=%s'
            params.append(category)
        stays = query(sql + ' ORDER BY id', params)
        saved = {r['stay_id'] for r in query('SELECT stay_id FROM wishlists WHERE user_id=%s', (g.user['id'],))} if g.user else set()
        return render_template('home.html', stays=stays, saved=saved, destination=destination, category=category)

    def auth_page(mode, error=None, status=200):
        return render_template('auth.html', mode=mode, error=error), status

    def after_login():
        stay_id = session.pop('booking_return', None)
        return redirect(url_for('stay_detail', stay_id=stay_id) if stay_id else url_for('home'))

    @app.route('/signup', methods=['GET', 'POST'])
    def signup():
        if g.user:
            return redirect(url_for('home'))
        if request.method == 'POST':
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
            if not 2 <= len(name) <= 80:
                return auth_page('signup', 'Enter a name between 2 and 80 characters.', 400)
            if len(email) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
                return auth_page('signup', 'Enter a valid email address.', 400)
            if not 8 <= len(password) <= 128:
                return auth_page('signup', 'Use a password between 8 and 128 characters.', 400)
            if password != request.form.get('confirm_password'):
                return auth_page('signup', 'Your passwords do not match.', 400)
            try:
                with db().cursor() as cur:
                    cur.execute('INSERT INTO users (name,email,password_hash) VALUES (%s,%s,%s)',
                                (name, email, generate_password_hash(password, method='scrypt')))
                    uid = cur.lastrowid
                db().commit()
            except pymysql.err.IntegrityError:
                db().rollback()
                return auth_page('signup', 'An account already uses this email. Please log in.', 409)
            booking_return = session.get('booking_return')
            booking_draft = session.get('booking_draft')
            session.clear()
            session['booking_return'] = booking_return
            session['booking_draft'] = booking_draft
            session.update(user_id=uid, csrf=secrets.token_urlsafe(32))
            session.permanent = True
            flash('Welcome! Your account is ready. Start saving your favourite stays.', 'success')
            return after_login()
        return auth_page('signup')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if g.user:
            return redirect(url_for('home'))
        if request.method == 'POST':
            email = request.form.get('email', '').strip().lower()[:254]
            password = request.form.get('password', '')
            # Persist throttling in MySQL, shared across application workers.
            attempts = query('SELECT COUNT(*) AS n FROM login_attempts WHERE email=%s AND attempted_at > DATE_SUB(UTC_TIMESTAMP(), INTERVAL 15 MINUTE)', (email,), one=True)
            if attempts['n'] >= 10:
                return auth_page('login', 'Too many attempts. Please try again in 15 minutes.', 429)
            user = query('SELECT * FROM users WHERE email=%s', (email,), one=True)
            valid = check_password_hash(user['password_hash'] if user else app.config['DUMMY_HASH'], password[:129])
            if not user or not valid or len(password) > 128:
                with db().cursor() as cur:
                    cur.execute('INSERT INTO login_attempts (email) VALUES (%s)', (email,))
                    cur.execute('DELETE FROM login_attempts WHERE attempted_at < DATE_SUB(UTC_TIMESTAMP(), INTERVAL 1 DAY)')
                db().commit()
                return auth_page('login', 'Email or password is incorrect.', 401)
            with db().cursor() as cur:
                cur.execute('DELETE FROM login_attempts WHERE email=%s', (email,))
            db().commit()
            booking_return = session.get('booking_return')
            booking_draft = session.get('booking_draft')
            session.clear()
            session['booking_return'] = booking_return
            session['booking_draft'] = booking_draft
            session.update(user_id=user['id'], csrf=secrets.token_urlsafe(32))
            session.permanent = True
            flash('Welcome back, ' + user['name'] + '.', 'success')
            return after_login()
        return auth_page('login')

    app.config['DUMMY_HASH'] = generate_password_hash(secrets.token_urlsafe(32), method='scrypt')

    @app.post('/logout')
    def logout():
        session.clear()
        flash('You have been logged out.', 'info')
        return redirect(url_for('home'))

    @app.get('/wishlist')
    @login_required
    def wishlist():
        stays = query('SELECT s.* FROM stays s JOIN wishlists w ON w.stay_id=s.id WHERE w.user_id=%s ORDER BY w.created_at DESC', (g.user['id'],))
        return render_template('wishlist.html', stays=stays, saved={r['id'] for r in stays})

    @app.post('/wishlist/<int:stay_id>')
    @login_required
    def save_stay(stay_id):
        if not query('SELECT id FROM stays WHERE id=%s', (stay_id,), one=True):
            abort(404)
        action = request.form.get('action')
        if action not in ('save', 'remove'):
            abort(400)
        with db().cursor() as cur:
            if action == 'remove':
                cur.execute('DELETE FROM wishlists WHERE user_id=%s AND stay_id=%s', (g.user['id'], stay_id))
            else:
                cur.execute('INSERT IGNORE INTO wishlists (user_id,stay_id) VALUES (%s,%s)', (g.user['id'], stay_id))
        db().commit()
        flash('Stay removed from your wishlist.' if action == 'remove' else 'Stay saved to your wishlist.', 'success')
        return redirect(url_for('wishlist') if request.form.get('origin') == 'wishlist' else url_for('home', destination=request.form.get('destination', '')[:100], category=request.form.get('category', 'All homes')))

    @app.route('/stays/<int:stay_id>', methods=['GET', 'POST'])
    def stay_detail(stay_id):
        stay = query('SELECT * FROM stays WHERE id=%s', (stay_id,), one=True)
        if not stay:
            abort(404)
        match = re.search(r'(\d+) guests', stay['description'])
        capacity = int(match.group(1)) if match else 2
        today = datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
        values = {key: request.form.get(key, default) for key, default in
                  [('adults', '1'), ('children', '0'), ('check_in', ''), ('check_out', '')]}
        if request.method == 'GET':
            draft = session.pop('booking_draft', None)
            if draft and draft.get('stay_id') == stay_id:
                values.update(draft['values'])
        error = None
        if request.method == 'POST':
            if not g.user:
                session['booking_return'] = stay_id
                session['booking_draft'] = {'stay_id': stay_id, 'values': {key: value[:20] for key, value in values.items()}}
                flash('Please log in to book this stay.', 'info')
                return redirect(url_for('login'))
            try:
                adults, children = int(values['adults']), int(values['children'])
                check_in, check_out = date.fromisoformat(values['check_in']), date.fromisoformat(values['check_out'])
                if adults < 1 or children < 0 or adults + children > capacity:
                    raise ValueError('guests')
                if check_in < today or check_out <= check_in:
                    raise ValueError('dates')
            except (ValueError, OverflowError):
                error = f'Choose valid dates (check-out after check-in), at least one adult, and no more than {capacity} guests.'
            if not error:
                booking_token = request.form.get('booking_token', '')
                if not re.fullmatch(r'[a-f0-9]{32}', booking_token):
                    abort(400, 'Reload this page before booking.')
                # Serialize reservations for a property, including concurrent requests.
                stay = query('SELECT * FROM stays WHERE id=%s FOR UPDATE', (stay_id,), one=True)
                existing = query('SELECT id FROM bookings WHERE user_id=%s AND request_token=%s FOR UPDATE',
                                 (g.user['id'], booking_token), one=True)
                if existing:
                    db().rollback()
                    flash('This booking is already confirmed.', 'success')
                    return redirect(url_for('bookings'))
                overlap = query('SELECT id FROM bookings WHERE stay_id=%s AND check_in < %s AND check_out > %s FOR UPDATE',
                                (stay_id, check_out, check_in), one=True)
                if overlap:
                    db().rollback()
                    error = 'This property is already booked for those dates. Please choose another stay or different dates.'
                else:
                    nights = (check_out - check_in).days
                    with db().cursor() as cur:
                        cur.execute('INSERT INTO bookings (user_id,stay_id,check_in,check_out,adults,children,nightly_price,total_price,request_token) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                                    (g.user['id'], stay_id, check_in, check_out, adults, children, stay['price'], stay['price'] * nights, booking_token))
                    db().commit()
                    flash('Successfully booked! Your stay is confirmed. No payment is required.', 'success')
                    return redirect(url_for('bookings'))
        facilities = ['Wi-Fi', 'Kitchen', 'Fresh linens and towels', 'Free parking']
        if stay['category'] == 'Amazing pools':
            facilities.append('Swimming pool')
        return render_template('stay.html', stay=stay, capacity=capacity, today=today.isoformat(),
                               values=values, error=error, facilities=facilities,
                               booking_token=secrets.token_hex(16)), (400 if error else 200)

    @app.get('/booking')
    @app.get('/bookings')
    @login_required
    def bookings():
        rows = query('SELECT b.*, s.title, s.location, s.image FROM bookings b JOIN stays s ON s.id=b.stay_id WHERE b.user_id=%s ORDER BY b.created_at DESC, b.id DESC', (g.user['id'],))
        return render_template('bookings.html', bookings=rows)

    @app.get('/health')
    def health():
        query('SELECT 1')
        return {'status': 'ok'}

    @app.errorhandler(pymysql.MySQLError)
    def database_error(error):
        app.logger.error('Database request failed: %s', type(error).__name__)
        return render_template('error.html', code=503, message='We cannot connect right now. Please try again shortly.'), 503

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def client_error(error):
        return render_template('error.html', code=error.code, message=error.description), error.code

    @app.cli.command('init-db')
    def init_db():
        """Create tables and insert demonstration stays without deleting existing data."""
        with db().cursor() as cur:
            for statement in Path(app.root_path, 'schema.sql').read_text().split(';'):
                if statement.strip():
                    cur.execute(statement)
        db().commit()
        click.echo('MySQL tables and demo stays are ready.')

    return app
