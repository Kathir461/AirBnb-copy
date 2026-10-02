import os
import re
import uuid
from unittest.mock import MagicMock, patch
import pytest
import pymysql
from werkzeug.security import check_password_hash, generate_password_hash
from app import create_app

@pytest.fixture
def app():
    return create_app({'TESTING': True, 'SECRET_KEY': 'unit-test-only-' + 'x' * 40})

@pytest.fixture
def client(app):
    return app.test_client()

def token(client, path='/login'):
    result = client.get(path)
    assert result.status_code == 200
    with client.session_transaction() as session:
        return session['csrf']

@pytest.mark.parametrize('route', ['/login','/signup'])
def test_auth_pages(client, route):
    response = client.get(route)
    assert response.status_code == 200
    assert b'csrf_token' in response.data
    assert 'frame-ancestors' in response.headers['Content-Security-Policy']
    assert 'HttpOnly' in response.headers['Set-Cookie']

@pytest.mark.parametrize('route', ['/signup','/login','/logout','/wishlist/1'])
def test_post_requires_csrf(client, route):
    assert client.post(route).status_code == 400

def test_non_ascii_csrf_is_rejected(client):
    token(client)
    assert client.post('/logout', data={'csrf_token': 'தவறு'}).status_code == 400

def test_wishlist_requires_login(client):
    assert client.get('/wishlist').status_code == 302
    assert client.get('/wishlist').headers['Location'].endswith('/login')

def test_signup_validation_before_database(client):
    csrf = token(client, '/signup')
    result = client.post('/signup', data={'csrf_token': csrf,'name':'Alice','email':'invalid','password':'long-password','confirm_password':'long-password'})
    assert result.status_code == 400
    assert b'valid email' in result.data
    result = client.post('/signup', data={'csrf_token': csrf,'name':'Alice','email':'alice@example.com','password':'long-password','confirm_password':'different'})
    assert result.status_code == 400
    assert b'do not match' in result.data

def test_password_hash():
    hashed = generate_password_hash('test-password', method='scrypt')
    assert hashed != 'test-password' and hashed.startswith('scrypt:')
    assert check_password_hash(hashed, 'test-password')
    assert not check_password_hash(hashed, 'wrong-password')

def test_database_error_is_readable(client):
    with patch('app.pymysql.connect', side_effect=pymysql.err.OperationalError('private connection details')):
        response=client.get('/')
    assert response.status_code == 503
    assert b'private connection details' not in response.data
    assert b'cannot connect' in response.data

def test_catalog_renders_and_parameterizes_search(client):
    connection=MagicMock()
    cursor=connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value=[{'id':1,'title':'Test stay','location':'Chennai, India','category':'Design','description':'Entire home','price':5000,'rating':'4.98','image':'stay-1.jpg','badge':'Guest favourite'}]
    with patch('app.pymysql.connect', return_value=connection):
        response=client.get('/', query_string={'destination':"' OR 1=1 --"})
    assert response.status_code == 200
    assert b'Test stay' in response.data
    sql, params=cursor.execute.call_args.args
    assert "' OR 1=1 --" not in sql
    assert params[0] == "%' OR 1=1 --%"

def test_404(client):
    assert client.get('/does-not-exist').status_code == 404

@pytest.mark.skipif(os.getenv('RUN_MYSQL_TESTS') != '1', reason='Requires a dedicated running MySQL test database')
def test_mysql_accounts_wishlist_and_persistence(app):
    assert os.getenv('MYSQL_DATABASE','').endswith('_test'), 'Use a dedicated database ending in _test'
    assert app.test_cli_runner().invoke(args=['init-db']).exit_code == 0
    a,b=app.test_client(), app.test_client()
    emails=['clubtest-' + uuid.uuid4().hex + '@example.com' for _ in range(2)]
    password='Unique-test-password-2026!'
    def connection():
        kwargs=dict(host=os.getenv('MYSQL_HOST','127.0.0.1'),port=int(os.getenv('MYSQL_PORT','3306')),user=os.getenv('MYSQL_USER','stayuser'),password=os.environ['MYSQL_PASSWORD'],database=os.environ['MYSQL_DATABASE'],cursorclass=pymysql.cursors.DictCursor)
        if os.getenv('MYSQL_SSL_CA'): kwargs['ssl']={'ca':os.environ['MYSQL_SSL_CA'],'check_hostname':True}
        return pymysql.connect(**kwargs)
    try:
        for client,email in zip((a,b),emails):
            csrf=token(client,'/signup')
            response=client.post('/signup',data={'csrf_token':csrf,'name':'Test User','email':email,'password':password,'confirm_password':password})
            assert response.status_code == 302
        with a.session_transaction() as sess: csrf=sess['csrf']
        assert a.post('/wishlist/1', data={'csrf_token':csrf,'action':'save'}).status_code == 302
        assert b'The Palm House' in a.get('/wishlist').data
        assert b'The Palm House' not in b.get('/wishlist').data
        # Repeated save remains one row; deleting from B cannot delete A's data.
        a.post('/wishlist/1',data={'csrf_token':csrf,'action':'save'})
        with b.session_transaction() as sess: csrf_b=sess['csrf']
        b.post('/wishlist/1',data={'csrf_token':csrf_b,'action':'remove'})
        assert b'The Palm House' in a.get('/wishlist').data
        # A fresh MySQL connection confirms persistence and hashes.
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT id,password_hash FROM users WHERE email=%s',(emails[0],))
                user=cur.fetchone()
                assert check_password_hash(user['password_hash'],password)
                assert user['password_hash'] != password
                cur.execute('SELECT COUNT(*) AS n FROM wishlists WHERE user_id=%s',(user['id'],))
                assert cur.fetchone()['n'] == 1
        a.post('/logout',data={'csrf_token':csrf})
        assert a.get('/wishlist').status_code == 302
        csrf=token(a)
        assert a.post('/login',data={'csrf_token':csrf,'email':emails[0],'password':'wrong'}).status_code == 401
        assert a.post('/login',data={'csrf_token':csrf,'email':emails[0],'password':password}).status_code == 302
        assert b'The Palm House' in a.get('/wishlist').data
        with a.session_transaction() as sess: csrf=sess['csrf']
        assert a.post('/wishlist/1',data={'csrf_token':csrf,'action':'remove'}).status_code == 302
        assert b'The Palm House' not in a.get('/wishlist').data
        a.post('/logout',data={'csrf_token':csrf})
        csrf=token(a,'/signup')
        assert a.post('/signup',data={'csrf_token':csrf,'name':'Duplicate','email':emails[0],'password':password,'confirm_password':password}).status_code == 409
    finally:
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute('DELETE FROM users WHERE email IN (%s,%s)',emails)
                cur.execute('DELETE FROM login_attempts WHERE email IN (%s,%s)',emails)
            conn.commit()
from datetime import date, timedelta

@pytest.fixture
def booking_db(client):
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    stay = {'id': 1, 'title': 'Test villa', 'location': 'India', 'category': 'Amazing pools',
            'description': 'Entire villa · 6 guests · 3 bedrooms', 'price': 8500,
            'rating': '4.98', 'image': 'stay-1.jpg'}
    state = {'overlap': False, 'existing': False}
    def fetch(sql, args=()):
        if 'FROM users' in sql:
            cursor.fetchone.return_value = {'id': 7, 'name': 'Test User', 'email': 'test@example.com'}
        elif 'SELECT * FROM stays' in sql:
            cursor.fetchone.return_value = stay
        elif 'request_token=' in sql:
            cursor.fetchone.return_value = {'id': 3} if state['existing'] else None
        elif 'check_in <' in sql:
            cursor.fetchone.return_value = {'id': 2} if state['overlap'] else None
        else:
            cursor.fetchone.return_value = {'id': 1}
    cursor.execute.side_effect = fetch
    cursor.fetchall.return_value = []
    with client.session_transaction() as sess:
        sess.update(user_id=7, csrf='test-csrf')
    with patch('app.pymysql.connect', return_value=connection):
        yield connection, cursor, state


def booking_data(**changes):
    data = dict(csrf_token='test-csrf', booking_token='a' * 32, adults='2', children='1',
                check_in=(date.today() + timedelta(days=10)).isoformat(),
                check_out=(date.today() + timedelta(days=13)).isoformat())
    data.update(changes)
    return data


def test_detail_and_booking_price(client, booking_db):
    connection, cursor, _ = booking_db
    response = client.get('/stays/1')
    assert response.status_code == 200
    assert b'Room details' in response.data and b'Swimming pool' in response.data
    assert response.data.index(b'Room details') < response.data.index(b'Property facilities')
    response = client.post('/stays/1', data=booking_data(total_price='1'))
    assert response.status_code == 302 and response.location.endswith('/bookings')
    inserts = [call.args for call in cursor.execute.call_args_list if 'INSERT INTO bookings' in call.args[0]]
    assert len(inserts) == 1
    assert inserts[0][1][4:8] == (2, 1, 8500, 25500)
    connection.commit.assert_called_once()
    response = client.get('/bookings')
    assert b'Successfully booked!' in response.data
    assert cursor.execute.call_args.args[1] == (7,)


@pytest.mark.parametrize('changes', [dict(adults='0'), dict(children='-1'), dict(children='5'),
    dict(adults='1.5'), dict(check_in='bad'), dict(check_in='2020-01-01'),
    dict(check_out=(date.today() + timedelta(days=10)).isoformat()),
    dict(check_out=(date.today() + timedelta(days=9)).isoformat())])
def test_invalid_booking_never_writes(client, booking_db, changes):
    connection, cursor, _ = booking_db
    assert client.post('/stays/1', data=booking_data(**changes)).status_code == 400
    connection.commit.assert_not_called()
    assert not any('INSERT INTO bookings' in call.args[0] for call in cursor.execute.call_args_list)


def test_overlap_and_repeat_submission(client, booking_db):
    connection, cursor, state = booking_db
    state['overlap'] = True
    response = client.post('/stays/1', data=booking_data())
    assert response.status_code == 400 and b'already booked' in response.data
    connection.commit.assert_not_called()
    state['existing'] = True
    assert client.post('/stays/1', data=booking_data()).status_code == 302
    connection.commit.assert_not_called()
    assert not any('INSERT INTO bookings' in call.args[0] for call in cursor.execute.call_args_list)


def test_booking_login_and_csrf(client, booking_db):
    with client.session_transaction() as sess:
        sess.pop('user_id')
    assert client.get('/booking').location.endswith('/login')
    assert client.post('/stays/1').status_code == 400
    assert client.post('/stays/1', data=booking_data()).location.endswith('/login')
    with client.session_transaction() as sess:
        assert sess['booking_return'] == 1


def test_bookings_render_saved_price_and_duration(client, booking_db):
    _, cursor, _ = booking_db
    cursor.fetchall.return_value = [dict(id=4, stay_id=1, title='Test villa', location='India',
        image='stay-1.jpg', adults=2, children=1, check_in=date(2026, 11, 1),
        check_out=date(2026, 11, 4), nightly_price=8500, total_price=25500)]
    response = client.get('/bookings')
    assert response.status_code == 200
    assert b'25,500' in response.data and b'4 days' in response.data and b'3 nights' in response.data
    assert cursor.execute.call_args.args[1] == (7,)

def test_login_preserves_booking_selection(client, booking_db):
    _, cursor, _ = booking_db
    with client.session_transaction() as sess:
        sess.pop('user_id')
    data = booking_data()
    client.post('/stays/1', data=data)
    cursor.execute.side_effect = None
    cursor.fetchone.side_effect = [{'n': 0}, {'id': 7, 'name': 'Test User', 'password_hash': generate_password_hash('valid-password', method='scrypt')}]
    response = client.post('/login', data={'csrf_token': 'test-csrf', 'email': 'test@example.com', 'password': 'valid-password'})
    assert response.location.endswith('/stays/1')
    with client.session_transaction() as sess:
        assert sess['user_id'] == 7
        assert sess['booking_draft']['values']['check_in'] == data['check_in']
        assert sess['booking_draft']['values']['children'] == '1'


def test_missing_property(client, booking_db):
    _, cursor, _ = booking_db
    cursor.execute.side_effect = None
    cursor.fetchone.side_effect = [{'id': 7, 'name': 'Test User'}, None]
    assert client.get('/stays/999').status_code == 404
