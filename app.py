import base64
import binascii
from contextlib import closing
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
from uuid import uuid4

from flask import Flask, abort, jsonify, render_template, request, send_from_directory, session, url_for

app = Flask(__name__)
Path(app.instance_path).mkdir(parents=True, exist_ok=True)
SECRET_KEY_FILE = Path(app.instance_path) / 'secret_key'
app.secret_key = os.environ.get('FLASK_SECRET_KEY')
if not app.secret_key:
    if not SECRET_KEY_FILE.exists():
        SECRET_KEY_FILE.write_text(secrets.token_hex(32), encoding='utf-8')
    app.secret_key = SECRET_KEY_FILE.read_text(encoding='utf-8').strip()
app.config['ADMIN_USERNAME'] = os.environ.get('ADMIN_USERNAME', 'admin')
app.config['ADMIN_PASSWORD'] = os.environ.get('ADMIN_PASSWORD', '123456')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE') == '1'
DATABASE_FILE = Path(app.instance_path) / 'tech_house.db'
LEGACY_PRODUCTS_FILE = Path(app.instance_path) / 'products.json'
DEFAULT_PRODUCT_IMAGE = 'https://images.unsplash.com/photo-1552664730-d307ca884978?auto=format&fit=crop&w=1200&q=80'

PRODUCTS = [
    {
        'id': 'cam-01',
        'name': 'كاميرا مراقبة 4K Pro',
        'category': 'أمن',
        'badge': 'مميز',
        'price': 'LE 3,200',
        'oldPrice': 'LE 4,100',
        'description': 'كاميرا خارجية عالية الدقة مع رؤية ليلية قوية وتسجيل مستمر ومقاومة للماء.',
        'specs': ['دقة 4K Ultra HD', 'رؤية ليلية حتى 30 متر', 'حماية IP66', 'تثبيت سهل وسريع'],
        'images': [
            'https://images.unsplash.com/photo-1555618561-2e7a48b3c2c0?auto=format&fit=crop&w=1200&q=80',
            'https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80',
            'https://images.unsplash.com/photo-1581092921461-eab62e97a780?auto=format&fit=crop&w=1200&q=80'
        ]
    },
    {
        'id': 'net-02',
        'name': 'موجه شبكة SMB Pro',
        'category': 'شبكات',
        'badge': 'جديد',
        'price': 'LE 2,600',
        'oldPrice': 'LE 3,300',
        'description': 'موجه شبكة احترافي يدعم أداء متوازن للمنزل والعمل مع تحكم سهل واتصال مستقر.',
        'specs': ['سرعة حتى 1.2 Gbps', '4 منافذ LAN', 'حماية WPA3', 'واجهة سهلة الإدارة'],
        'images': [
            'https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=1200&q=80',
            'https://images.unsplash.com/photo-1542744173-8e7e534b2089?auto=format&fit=crop&w=1200&q=80'
        ]
    },
    {
        'id': 'dev-03',
        'name': 'لوحة تحكم ذكية Home Hub',
        'category': 'أجهزة',
        'badge': 'متميز',
        'price': 'LE 1,900',
        'oldPrice': 'LE 2,300',
        'description': 'لوحة تحكم مركزية لإدارة الأجهزة الذكية في المنزل أو المكتب بسهولة عالية.',
        'specs': ['دعم Zigbee + WiFi', 'تحكم صوتي', 'إدارة أوتوماتيك', 'واجهة عربية'],
        'images': [
            'https://images.unsplash.com/photo-1516321497487-e288fb19713f?auto=format&fit=crop&w=1200&q=80',
            'https://images.unsplash.com/photo-1498050108023-c5249f4df085?auto=format&fit=crop&w=1200&q=80'
        ]
    },
    {
        'id': 'svc-04',
        'name': 'خدمة تركيب وصيانة الأنظمة',
        'category': 'خدمات',
        'badge': 'استشارة مجانية',
        'price': 'تواصل للاستشارة',
        'oldPrice': '',
        'description': 'خدمة تركيب شبكات وأنظمة أمنية مع مراجعة فنية، ضبط إعدادات، وتوجيه فني حسب الموقع.',
        'specs': ['دراسة الموقع', 'تركيب احترافي', 'ضبط وإعداد', 'دعم فني مستمر'],
        'images': [
            'https://images.unsplash.com/photo-1522202176988-66273c2fd55f?auto=format&fit=crop&w=1200&q=80',
            'https://images.unsplash.com/photo-1552664730-d307ca884978?auto=format&fit=crop&w=1200&q=80'
        ]
    },
    {
        'id': 'cam-05',
        'name': 'نظام كاميرات تجاري',
        'category': 'أمن',
        'badge': 'أفضل اختيار',
        'price': 'LE 5,400',
        'oldPrice': 'LE 6,500',
        'description': 'حل كامل للمؤسسات والورش مع ربط متعدد، مراقبة مباشرة، ونسخ احتياطي ذكي.',
        'specs': ['8 كاميرات متوافقة', 'تخزين موسع', 'مراقبة عبر الهاتف', 'تسجيل 24/7'],
        'images': [
            'https://images.unsplash.com/photo-1581092160607-ee2279d0f0d7?auto=format&fit=crop&w=1200&q=80',
            'https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=1200&q=80'
        ]
    }
]


def initialize_database():
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(DATABASE_FILE)) as connection, connection:
        table_exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'products'"
        ).fetchone() is not None
        connection.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                price TEXT NOT NULL DEFAULT '',
                badge TEXT NOT NULL DEFAULT '',
                image TEXT NOT NULL DEFAULT '',
                position INTEGER NOT NULL DEFAULT 0
            )
        ''')
        existing_columns = {
            row[1] for row in connection.execute('PRAGMA table_info(products)')
        }
        migrations = {
            'old_price': "TEXT NOT NULL DEFAULT ''",
            'specs_json': "TEXT NOT NULL DEFAULT '[]'",
            'images_json': "TEXT NOT NULL DEFAULT '[]'"
        }
        for column, definition in migrations.items():
            if column not in existing_columns:
                connection.execute(f'ALTER TABLE products ADD COLUMN {column} {definition}')

        legacy_images = connection.execute(
            "SELECT id, image FROM products WHERE images_json = '[]' AND image != ''"
        ).fetchall()
        for product_id, image in legacy_images:
            connection.execute(
                'UPDATE products SET images_json = ? WHERE id = ?',
                (json.dumps([image]), product_id)
            )

        if not table_exists:
            initial_products = PRODUCTS
            if LEGACY_PRODUCTS_FILE.exists():
                try:
                    with LEGACY_PRODUCTS_FILE.open(encoding='utf-8') as legacy_file:
                        legacy_products = json.load(legacy_file)
                    if isinstance(legacy_products, list) and legacy_products:
                        initial_products = legacy_products
                except (OSError, json.JSONDecodeError):
                    pass
            _replace_products(connection, initial_products)


def _replace_products(connection, products):
    connection.execute('DELETE FROM products')
    for position, product in enumerate(products, start=1):
        images = product.get('images') or ([product.get('image')] if product.get('image') else [])
        if not images:
            images = [DEFAULT_PRODUCT_IMAGE]
        specs = product.get('specs') or []
        connection.execute('''
            INSERT INTO products (
                id, name, category, description, price, badge, image,
                position, old_price, specs_json, images_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            str(product['id']),
            product['name'],
            product.get('category') or '',
            product.get('description') or '',
            str(product.get('price') or ''),
            product.get('badge') or '',
            images[0],
            position,
            str(product.get('oldPrice') or product.get('old_price') or ''),
            json.dumps(specs, ensure_ascii=False),
            json.dumps(images, ensure_ascii=False)
        ))


def load_products():
    initialize_database()
    with closing(sqlite3.connect(DATABASE_FILE)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute('SELECT * FROM products ORDER BY position, id').fetchall()

    products = []
    for row in rows:
        try:
            images = json.loads(row['images_json'] or '[]')
        except (json.JSONDecodeError, TypeError):
            images = []
        if not isinstance(images, list) or not images:
            images = [row['image'] or DEFAULT_PRODUCT_IMAGE]
        try:
            specs = json.loads(row['specs_json'] or '[]')
        except (json.JSONDecodeError, TypeError):
            specs = []
        products.append({
            'id': str(row['id']),
            'name': row['name'],
            'category': row['category'],
            'description': row['description'],
            'price': row['price'],
            'badge': row['badge'],
            'oldPrice': row['old_price'],
            'specs': specs if isinstance(specs, list) else [],
            'images': images
        })
    return products


def save_products(products):
    initialize_database()
    with closing(sqlite3.connect(DATABASE_FILE)) as connection, connection:
        _replace_products(connection, products)


initialize_database()


def prepare_product_images(products):
    upload_dir = Path(app.instance_path) / 'uploads'
    upload_dir.mkdir(parents=True, exist_ok=True)

    for product in products:
        images = product.get('images', [])
        if not isinstance(images, list):
            return False
        public_images = []
        for image in images:
            if not isinstance(image, str) or not image.startswith('data:image/'):
                public_images.append(image)
                continue
            try:
                header, encoded = image.split(',', 1)
                mime_type = header[5:].split(';', 1)[0]
                extension = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp', 'image/gif': '.gif'}.get(mime_type)
                if not extension or ';base64' not in header:
                    return False
                filename = f'{uuid4().hex}{extension}'
                image_bytes = base64.b64decode(encoded, validate=True)
                (upload_dir / filename).write_bytes(image_bytes)
                public_images.append(url_for('uploaded_product_image', filename=filename))
            except (ValueError, binascii.Error, OSError):
                return False
        product['images'] = public_images
    return True


@app.route('/')
def home():
    return render_template('index.html', products=load_products())


@app.route('/api/products', methods=['GET', 'PUT'])
def products_api():
    if request.method == 'GET':
        return jsonify({
            'products': load_products(),
            'needs_import': False
        })

    if not session.get('admin_authenticated'):
        return jsonify({'error': 'Admin login required'}), 401

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({'error': 'A JSON object is required'}), 400
    products = payload.get('products')
    if not isinstance(products, list):
        return jsonify({'error': 'products must be a list'}), 400

    product_ids = set()
    for product in products:
        if not isinstance(product, dict) or not isinstance(product.get('name'), str) or not product['name'].strip():
            return jsonify({'error': 'Each product must have an id and name'}), 400
        product_id = product.get('id')
        if isinstance(product_id, bool) or not isinstance(product_id, (str, int)):
            return jsonify({'error': 'Each product must have an id and name'}), 400
        product['id'] = str(product_id).strip()
        if not product['id']:
            return jsonify({'error': 'Each product must have an id and name'}), 400
        if product['id'] in product_ids:
            return jsonify({'error': 'Product IDs must be unique'}), 400
        product_ids.add(product['id'])

    if not prepare_product_images(products):
        return jsonify({'error': 'Product images must be valid PNG, JPEG, WEBP, or GIF images'}), 400

    save_products(products)
    return jsonify({'products': products, 'needs_import': False})


@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({'error': 'A JSON object is required'}), 400

    username = str(payload.get('username', ''))
    password = str(payload.get('password', ''))
    valid_username = hmac.compare_digest(username, app.config['ADMIN_USERNAME'])
    valid_password = hmac.compare_digest(password, app.config['ADMIN_PASSWORD'])
    if not valid_username or not valid_password:
        return jsonify({'error': 'Invalid username or password'}), 401

    session['admin_authenticated'] = True
    return jsonify({'authenticated': True})


@app.route('/api/admin/logout', methods=['POST'])
def admin_logout():
    session.clear()
    return jsonify({'authenticated': False})


@app.route('/api/admin/session')
def admin_session():
    return jsonify({'authenticated': bool(session.get('admin_authenticated'))})


@app.route('/uploads/<path:filename>')
def uploaded_product_image(filename):
    upload_dir = Path(app.instance_path) / 'uploads'
    image_path = upload_dir / filename
    if not image_path.is_file() or image_path.parent != upload_dir:
        abort(404)
    return send_from_directory(upload_dir, filename)


@app.route('/product/<product_id>')
def product_detail(product_id):
    products = load_products()
    product = next((item for item in products if str(item.get('id')) == product_id), None)
    if product is None:
        return render_template('product_not_found.html', product_id=product_id), 404
    return render_template('product.html', product=product)


@app.route('/admin')
def admin_route():
    return render_template('index.html', products=load_products())


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
