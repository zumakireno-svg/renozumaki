import base64
import binascii
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
from uuid import uuid4
from urllib.parse import urlsplit
from contextlib import contextmanager

from flask import Flask, Response, abort, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY') or os.environ.get('FLASK_SECRET_KEY') or secrets.token_hex(32),
    SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.environ.get('SESSION_COOKIE_SECURE', '').lower() in ('1', 'true'),
    MAX_CONTENT_LENGTH=40 * 1024 * 1024,
)

def format_product_price(value):
    """Show numeric catalog prices with the Egyptian pound abbreviation."""
    price = str(value or '').strip()
    if not price:
        return ''
    price = re.sub(r'^(?:EGP|LE|L\.E\.|جنيه(?:اً)?|ج\.?\s*م\.?)\s*', '', price, flags=re.IGNORECASE)
    price = re.sub(r'\s*(?:EGP|LE|L\.E\.|جنيه(?:اً)?|ج\.?\s*م\.?)$', '', price, flags=re.IGNORECASE)
    if not any(char.isdigit() for char in price):
        return str(value).strip()
    return f'EGP {price}'

app.jinja_env.filters['egp_price'] = format_product_price

def resolve_database_url():
    preferred = ('DATABASE_URL', 'POSTGRES_URL', 'POSTGRES_PRISMA_URL', 'POSTGRES_URL_NON_POOLING', 'NEON_DATABASE_URL')
    for name in preferred:
        if os.environ.get(name, '').strip():
            return os.environ[name].strip()
    # Marketplace integrations can prepend a custom prefix to injected variable names.
    for name, value in os.environ.items():
        if value.strip() and name.endswith(('_DATABASE_URL', '_POSTGRES_URL', '_POSTGRES_PRISMA_URL', '_POSTGRES_URL_NON_POOLING')):
            return value.strip()
    return ''

DATABASE_URL = resolve_database_url()
# Set only by isolated tests. The running application never falls back to local files.
DATABASE_FILE = None
LEGACY_PRODUCTS_FILE = Path(app.instance_path) / 'products.json'
DEFAULT_PRODUCT_IMAGE = 'https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&h=630&q=80'
PRODUCTS = [
 {'id':'cam-01','name':'كاميرا مراقبة 4K Pro','category':'أمن','badge':'مميز','price':'LE 3,200','oldPrice':'LE 4,100','description':'كاميرا خارجية عالية الدقة مع رؤية ليلية قوية وتسجيل مستمر ومقاومة للماء.','specs':['دقة 4K Ultra HD','رؤية ليلية حتى 30 متر','حماية IP66','تثبيت سهل وسريع'],'images':['https://images.unsplash.com/photo-1555618561-2e7a48b3c2c0?auto=format&fit=crop&w=1200&q=80']},
 {'id':'net-02','name':'موجه شبكة SMB Pro','category':'شبكات','badge':'جديد','price':'LE 2,600','oldPrice':'LE 3,300','description':'موجه شبكة احترافي يدعم أداء متوازن للمنزل والعمل مع تحكم سهل واتصال مستقر.','specs':['سرعة حتى 1.2 Gbps','4 منافذ LAN','حماية WPA3'],'images':['https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=1200&q=80']},
 {'id':'dev-03','name':'لوحة تحكم ذكية Home Hub','category':'أجهزة','badge':'متميز','price':'LE 1,900','oldPrice':'LE 2,300','description':'لوحة تحكم مركزية لإدارة الأجهزة الذكية في المنزل أو المكتب بسهولة عالية.','specs':['دعم Zigbee + WiFi','تحكم صوتي'],'images':['https://images.unsplash.com/photo-1516321497487-e288fb19713f?auto=format&fit=crop&w=1200&q=80']},
 {'id':'svc-04','name':'خدمة تركيب وصيانة الأنظمة','category':'خدمات','badge':'استشارة مجانية','price':'تواصل للاستشارة','oldPrice':'','description':'خدمة تركيب شبكات وأنظمة أمنية مع مراجعة فنية وضبط إعدادات.','specs':['دراسة الموقع','تركيب احترافي'],'images':['https://images.unsplash.com/photo-1522202176988-66273c2fd55f?auto=format&fit=crop&w=1200&q=80']},
 {'id':'cam-05','name':'نظام كاميرات تجاري','category':'أمن','badge':'أفضل اختيار','price':'LE 5,400','oldPrice':'LE 6,500','description':'حل كامل للمؤسسات والورش مع ربط متعدد ومراقبة مباشرة ونسخ احتياطي ذكي.','specs':['8 كاميرات متوافقة','تخزين موسع'],'images':['https://images.unsplash.com/photo-1581092160607-ee2279d0f0d7?auto=format&fit=crop&w=1200&q=80']}
]

@contextmanager
def database_connection():
    """Connect to persistent Postgres in every runtime; SQLite is test-only."""
    if DATABASE_URL:
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as error:
            raise RuntimeError('Install the psycopg[binary] dependency to use the configured Postgres database') from error
        connection = psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=10)
    elif app.config.get('TESTING') and DATABASE_FILE is not None:
        connection = sqlite3.connect(DATABASE_FILE)
        connection.row_factory = sqlite3.Row
    else:
        raise RuntimeError('A persistent PostgreSQL database is required. Configure DATABASE_URL or POSTGRES_URL in the deployment environment.')
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

def execute(db, sql, params=()):
    if DATABASE_URL:
        sql = sql.replace('?', '%s')
    return db.execute(sql, params)

def initialize_database():
    with database_connection() as db:
        if DATABASE_URL:
            exists = execute(db, "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_schema=current_schema() AND table_name='products') AS present").fetchone()['present']
        else:
            exists = execute(db, "SELECT 1 FROM sqlite_master WHERE type='table' AND name='products'").fetchone() is not None
        execute(db, """CREATE TABLE IF NOT EXISTS products (id TEXT PRIMARY KEY,name TEXT NOT NULL,category TEXT NOT NULL DEFAULT '',description TEXT NOT NULL DEFAULT '',price TEXT NOT NULL DEFAULT '',badge TEXT NOT NULL DEFAULT '',image TEXT NOT NULL DEFAULT '',position INTEGER NOT NULL DEFAULT 0)""")
        if DATABASE_URL:
            cols = {r['column_name'] for r in execute(db, "SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='products'")}
        else:
            cols = {r['name'] for r in execute(db, 'PRAGMA table_info(products)')}
        for col, definition in {'old_price':"TEXT NOT NULL DEFAULT ''",'specs_json':"TEXT NOT NULL DEFAULT '[]'",'images_json':"TEXT NOT NULL DEFAULT '[]'"}.items():
            if col not in cols: execute(db, f'ALTER TABLE products ADD COLUMN {col} {definition}')
        # Migrate the prior single-image schema without relying on SQLite-only JSON functions.
        for row in execute(db, "SELECT id,image FROM products WHERE images_json='[]' AND image!=''").fetchall():
            execute(db, 'UPDATE products SET images_json=? WHERE id=?', (json.dumps([row['image']]), row['id']))
        if not exists:
            initial = PRODUCTS
            if LEGACY_PRODUCTS_FILE.exists():
                try:
                    legacy=json.loads(LEGACY_PRODUCTS_FILE.read_text(encoding='utf-8'))
                    if isinstance(legacy,list) and legacy: initial=legacy
                except (OSError, ValueError): pass
            _replace_products(db, initial)
        execute(db, '''CREATE TABLE IF NOT EXISTS admin_account (id INTEGER PRIMARY KEY CHECK(id=1), username TEXT NOT NULL, password_hash TEXT NOT NULL)''')
        execute(db, '''CREATE TABLE IF NOT EXISTS product_images (id TEXT PRIMARY KEY, mime_type TEXT NOT NULL, image_data BYTEA NOT NULL)''')
        # One-time migration of the old environment credential; never use a built-in password.
        if not execute(db, 'SELECT 1 FROM admin_account WHERE id=1').fetchone():
            initial_password=os.environ.get('ADMIN_PASSWORD')
            if initial_password and len(initial_password) >= 12:
                execute(db, 'INSERT INTO admin_account(id,username,password_hash) VALUES(1,?,?)', (os.environ.get('ADMIN_USERNAME','admin'),generate_password_hash(initial_password)))

def _replace_products(db, products):
    for position, p in enumerate(products,1):
        images=p.get('images') or ([p.get('image')] if p.get('image') else [DEFAULT_PRODUCT_IMAGE])
        execute(db, '''INSERT INTO products(id,name,category,description,price,badge,image,position,old_price,specs_json,images_json) VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,category=excluded.category,description=excluded.description,price=excluded.price,badge=excluded.badge,image=excluded.image,position=excluded.position,old_price=excluded.old_price,specs_json=excluded.specs_json,images_json=excluded.images_json''', (str(p['id']),p.get('name',''),p.get('category',''),p.get('description',''),str(p.get('price','')),p.get('badge',''),images[0],position,str(p.get('oldPrice',p.get('old_price',''))),json.dumps(p.get('specs',[]),ensure_ascii=False),json.dumps(images,ensure_ascii=False)))

def load_products():
    initialize_database()
    with database_connection() as db:
        rows=execute(db, 'SELECT * FROM products ORDER BY position,id').fetchall()
    result=[]
    for r in rows:
        try: images=json.loads(r['images_json'] or '[]')
        except ValueError: images=[]
        try: specs=json.loads(r['specs_json'] or '[]')
        except ValueError: specs=[]
        result.append({'id':str(r['id']),'name':r['name'],'category':r['category'],'description':r['description'],'price':r['price'],'badge':r['badge'],'oldPrice':r['old_price'],'specs':specs if isinstance(specs,list) else [],'images':images if isinstance(images,list) and images else [r['image'] or DEFAULT_PRODUCT_IMAGE]})
    return result

def csrf_token():
    if '_csrf' not in session: session['_csrf']=secrets.token_urlsafe(32)
    return session['_csrf']

app.jinja_env.globals['csrf_token']=csrf_token
@app.before_request
def protect_csrf():
    if request.method in ('POST','PUT','PATCH','DELETE'):
        expected=session.get('_csrf','')
        supplied=request.form.get('csrf_token') or request.headers.get('X-CSRF-Token','')
        if not expected or not supplied or not secrets.compare_digest(expected,supplied): abort(400)

@app.route('/api/admin/csrf')
def admin_csrf(): return jsonify({'csrf_token': csrf_token()})

def base_url():
    configured=os.environ.get('PUBLIC_BASE_URL','').strip().rstrip('/')
    if configured: return configured.replace('http://','https://',1)
    return 'https://' + request.host

def absolute_public_image(image):
    if not image: image=DEFAULT_PRODUCT_IMAGE
    if image.startswith('/'): return base_url()+image
    return image

def decode_uploaded_image(data_url):
    try:
        header, encoded = data_url.split(',', 1)
        mime = header[5:].split(';', 1)[0]
        raw = base64.b64decode(encoded, validate=True)
        valid_magic = (mime == 'image/jpeg' and raw.startswith(b'\xff\xd8\xff')) or (mime == 'image/png' and raw.startswith(b'\x89PNG\r\n\x1a\n')) or (mime == 'image/gif' and raw.startswith((b'GIF87a', b'GIF89a'))) or (mime == 'image/webp' and len(raw) > 12 and raw.startswith(b'RIFF') and raw[8:12] == b'WEBP')
        if ';base64' not in header or not valid_magic or len(raw) > 3 * 1024 * 1024:
            return None
        return raw, mime
    except (ValueError, binascii.Error):
        return None

@app.route('/')
def home(): return render_template('index.html',products=load_products())

@app.route('/api/products',methods=['GET','PUT'])
def products_api():
    if request.method=='GET': return jsonify({'products':load_products(),'needs_import':False})
    if not session.get('admin_authenticated'): return jsonify({'error':'Admin login required'}),401
    payload=request.get_json(silent=True)
    if not isinstance(payload,dict) or not isinstance(payload.get('products'),list): return jsonify({'error':'Invalid product data'}),400
    products=payload['products']; ids=set(); uploaded_images={}
    for p in products:
        if not isinstance(p,dict) or not isinstance(p.get('name'),str) or not p['name'].strip() or not isinstance(p.get('id'),(str,int)) or isinstance(p.get('id'),bool): return jsonify({'error':'Invalid product data'}),400
        p['id']=str(p['id']).strip()
        if not p['id'] or p['id'] in ids: return jsonify({'error':'Invalid product data'}),400
        ids.add(p['id'])
        images=p.get('images',[])
        if not isinstance(images,list) or len(images)>8: return jsonify({'error':'Invalid product images'}),400
        for i,image in enumerate(images):
            if not isinstance(image,str): return jsonify({'error':'Invalid product images'}),400
            if not image.startswith('data:image/'):
                parsed=urlsplit(image)
                if parsed.scheme not in ('https','http') and not (not parsed.scheme and image.startswith(('/uploads/','/static/'))):
                    return jsonify({'error':'Invalid product images'}),400
            if image.startswith('data:image/'):
                decoded=decode_uploaded_image(image)
                if not decoded: return jsonify({'error':'صورة غير صالحة أو حجمها أكبر من 3 ميجابايت.'}),400
                name=uuid4().hex; uploaded_images[name]=(decoded[1],decoded[0]); images[i]='/uploads/'+name
        p['images']=images or [DEFAULT_PRODUCT_IMAGE]
    initialize_database()
    with database_connection() as db:
        for image_id, (mime, raw) in uploaded_images.items():
            execute(db, 'INSERT INTO product_images(id,mime_type,image_data) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET mime_type=excluded.mime_type,image_data=excluded.image_data', (image_id, mime, raw))
        execute(db, 'DELETE FROM products'); _replace_products(db,products)
        referenced=set()
        for row in execute(db, 'SELECT images_json FROM products').fetchall():
            try: urls=json.loads(row['images_json'] or '[]')
            except ValueError: urls=[]
            for url in urls if isinstance(urls,list) else []:
                if isinstance(url,str) and url.startswith('/uploads/'):
                    referenced.add(url.rsplit('/',1)[-1])
        for row in execute(db, 'SELECT id FROM product_images').fetchall():
            if row['id'] not in referenced: execute(db, 'DELETE FROM product_images WHERE id=?',(row['id'],))
    return jsonify({'products':products,'needs_import':False})

_login_failures={}
@app.route('/api/admin/login',methods=['POST'])
def admin_login():
    now=time.time(); key=request.remote_addr or 'unknown'; attempts=[t for t in _login_failures.get(key,[]) if now-t<600]
    if len(attempts)>=5: return jsonify({'error':'تعذر تسجيل الدخول. حاول لاحقاً.'}),429
    data=request.get_json(silent=True) or {}; username=str(data.get('username','')); password=str(data.get('password',''))
    initialize_database()
    with database_connection() as db: account=execute(db, 'SELECT username,password_hash FROM admin_account WHERE id=1').fetchone()
    valid=bool(account and secrets.compare_digest(username,account['username']) and check_password_hash(account['password_hash'],password))
    if not valid:
        attempts.append(now); _login_failures[key]=attempts
        return jsonify({'error':'اسم المستخدم أو كلمة المرور غير صحيحة'}),401
    _login_failures.pop(key,None); session.clear(); session['admin_authenticated']=True; session['admin_username']=username; csrf_token()
    return jsonify({'authenticated':True})

@app.route('/api/admin/logout',methods=['POST'])
def admin_logout(): session.clear(); return jsonify({'authenticated':False})
@app.route('/api/admin/session')
def admin_session(): return jsonify({'authenticated':bool(session.get('admin_authenticated')), 'username':session.get('admin_username') if session.get('admin_authenticated') else None})

@app.route('/uploads/<path:filename>')
def uploaded_product_image(filename):
    if not filename.isascii() or not filename.isalnum(): abort(404)
    initialize_database()
    with database_connection() as db:
        image=execute(db, 'SELECT mime_type,image_data FROM product_images WHERE id=?',(filename,)).fetchone()
    if not image: abort(404)
    response=Response(image['image_data'],mimetype=image['mime_type'])
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Cache-Control']='public, max-age=31536000, immutable'
    return response

@app.route('/product/<product_id>')
def product_detail(product_id):
    product=next((p for p in load_products() if p['id']==product_id),None)
    if not product: return render_template('product_not_found.html',product_id=product_id),404
    canonical=base_url()+url_for('product_detail',product_id=product['id'])
    image=absolute_public_image(product['images'][0])
    return render_template('product.html',product=product,canonical_url=canonical,social_image=image)

@app.route('/admin',methods=['GET','POST'])
def admin_route():
    initialize_database()
    with database_connection() as db: account=execute(db, 'SELECT 1 FROM admin_account WHERE id=1').fetchone()
    if not account: return redirect(url_for('admin_setup'))
    if session.get('admin_authenticated'): return redirect('/#admin')
    if request.method=='POST':
        data=request.form
        now=time.time(); key=request.remote_addr or 'unknown'; attempts=[t for t in _login_failures.get(key,[]) if now-t<600]
        if len(attempts)>=5: return render_template('admin_login.html',error='تعذر تسجيل الدخول. حاول لاحقاً.'),429
        with database_connection() as db: credential=execute(db, 'SELECT username,password_hash FROM admin_account WHERE id=1').fetchone()
        valid=bool(credential and secrets.compare_digest(data.get('username',''),credential['username']) and check_password_hash(credential['password_hash'],data.get('password','')))
        if not valid:
            attempts.append(now); _login_failures[key]=attempts
            return render_template('admin_login.html',error='اسم المستخدم أو كلمة المرور غير صحيحة'),401
        _login_failures.pop(key,None); session.clear(); session['admin_authenticated']=True; session['admin_username']=credential['username']; csrf_token()
        return redirect('/#admin')
    return render_template('admin_login.html',error=None)

@app.route('/admin/setup',methods=['GET','POST'])
def admin_setup():
    initialize_database()
    with database_connection() as db:
        account_exists=bool(execute(db, 'SELECT 1 FROM admin_account WHERE id=1').fetchone())
    setup_key=os.environ.get('SETUP_KEY','')
    # Existing accounts can only be recovered through this route when an
    # operator has explicitly enabled it with a deployment-only setup key.
    if account_exists and not setup_key: return redirect(url_for('admin_route'))
    error=None
    if request.method=='POST':
        password=request.form.get('password',''); username=request.form.get('username','admin').strip()
        now=time.time(); key='setup:'+str(request.remote_addr or 'unknown'); attempts=[t for t in _login_failures.get(key,[]) if now-t<600]
        if account_exists and len(attempts)>=5: return render_template('admin_setup.html',error='تعذر إكمال الإعداد. حاول لاحقاً.',needs_key=True,recovery=True,values={}),429
        if not username or len(username)>80: error='اكتب اسم مستخدم صالحاً.'
        elif len(password)<12 or password!=request.form.get('password2'): error='استخدم كلمة مرور من 12 حرفاً على الأقل وتأكد من تطابقها.'
        elif setup_key and not secrets.compare_digest(request.form.get('setup_key',''),setup_key):
            if account_exists:
                attempts.append(now); _login_failures[key]=attempts
            error='تعذر إكمال الإعداد.'
        else:
            with database_connection() as db:
                if account_exists:
                    execute(db, 'UPDATE admin_account SET username=?,password_hash=? WHERE id=1',(username,generate_password_hash(password)))
                else:
                    execute(db, 'INSERT INTO admin_account(id,username,password_hash) VALUES(1,?,?)',(username,generate_password_hash(password)))
            _login_failures.pop(key,None)
            session.clear(); session['admin_authenticated']=True; session['admin_username']=username; csrf_token()
            return redirect('/#admin')
    return render_template('admin_setup.html',error=error,needs_key=bool(setup_key),recovery=account_exists,values={})

@app.route('/admin/password',methods=['GET','POST'])
def admin_password():
    if not session.get('admin_authenticated'): return redirect(url_for('admin_route'))
    error=None
    if request.method=='POST':
        now=time.time(); key='password:'+str(request.remote_addr or 'unknown'); attempts=[t for t in _login_failures.get(key,[]) if now-t<600]
        if len(attempts)>=5: return render_template('admin_password.html',error='تعذر تغيير كلمة المرور. حاول لاحقاً.'),429
        current=request.form.get('current_password',''); new=request.form.get('new_password','')
        initialize_database()
        with database_connection() as db: row=execute(db, 'SELECT password_hash FROM admin_account WHERE id=1').fetchone()
        if not row or not check_password_hash(row['password_hash'],current):
            attempts.append(now); _login_failures[key]=attempts
            error='تعذر تغيير كلمة المرور. تحقق من البيانات وحاول مجدداً.'
        elif len(new)<12 or new!=request.form.get('confirm_password'): error='كلمة المرور الجديدة يجب أن تكون 12 حرفاً على الأقل وأن تتطابق مع التأكيد.'
        else:
            _login_failures.pop(key,None)
            with database_connection() as db: execute(db, 'UPDATE admin_account SET password_hash=? WHERE id=1',(generate_password_hash(new),))
            session.clear(); flash('تم تغيير كلمة المرور. سجّل الدخول مجدداً.'); return redirect(url_for('admin_route'))
    return render_template('admin_password.html',error=error)

@app.errorhandler(500)
def internal_error(error):
    app.logger.exception('Unhandled server error', exc_info=error.original_exception or error)
    return render_template('error.html', code=500, title='حدث خطأ في الخادم', message='تعذر إكمال الطلب. حاول مرة أخرى، وإذا استمرت المشكلة راجع سجل الأخطاء في Vercel.'),500

@app.errorhandler(400)
def bad_request(_error):
    return render_template('error.html', code=400, title='الطلب غير مكتمل', message='انتهت صلاحية النموذج أو تعذر التحقق منه. أعد تحميل الصفحة وحاول مجدداً.'),400

if __name__=='__main__': app.run()
