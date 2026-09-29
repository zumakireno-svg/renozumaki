import sqlite3
import base64
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import app as app_module
from werkzeug.security import generate_password_hash


class ProductSharingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_db, self.old_instance = app_module.DATABASE_FILE, app_module.app.instance_path
        app_module.DATABASE_FILE = Path(self.temp.name) / 'tech_house.db'
        app_module.app.instance_path = self.temp.name
        app_module.app.config['TESTING'] = True
        app_module.initialize_database()
        with closing(sqlite3.connect(app_module.DATABASE_FILE)) as db, db:
            db.execute('INSERT INTO admin_account(id,username,password_hash) VALUES(1,?,?)', ('admin', generate_password_hash('Long-test-passphrase-2026!')))
        app_module._login_failures.clear()
        self.client = app_module.app.test_client()

    def tearDown(self):
        app_module.DATABASE_FILE, app_module.app.instance_path = self.old_db, self.old_instance
        app_module.app.config['TESTING'] = False
        self.temp.cleanup()

    def csrf_headers(self):
        return {'X-CSRF-Token': self.client.get('/api/admin/csrf').get_json()['csrf_token']}

    def test_product_has_unique_escaped_https_share_metadata_and_fallback(self):
        with closing(sqlite3.connect(app_module.DATABASE_FILE)) as db, db:
            db.execute("INSERT INTO products(id,name,description,image,images_json) VALUES(?,?,?,?,?)", ('og-x','Camera <Pro> & "safe"','Description & <details>','', '[]'))
        response = self.client.get('/product/og-x', base_url='http://shop.example')
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn('https://shop.example/product/og-x', body)
        self.assertIn('og:title" content="Camera &lt;Pro&gt; &amp; &#34;safe&#34;', body)
        self.assertIn('og:image" content="https://images.unsplash.com/', body)
        self.assertEqual(body.count('property="og:image"'), 1)
        self.assertEqual(self.client.get('/product/missing').status_code, 404)

    def test_product_uses_its_own_public_image_and_canonical_route(self):
        with closing(sqlite3.connect(app_module.DATABASE_FILE)) as db, db:
            db.execute("INSERT INTO products(id,name,description,image,images_json) VALUES(?,?,?,?,?)", ('og-y','Different item','Separate description','https://cdn.example.org/different.webp','[\"https://cdn.example.org/different.webp\"]'))
        html=self.client.get('/product/og-y',base_url='https://shop.example').get_data(as_text=True)
        self.assertIn('og:title" content="Different item | بيت التكنولوجيا',html)
        self.assertIn('og:description" content="Separate description',html)
        self.assertIn('og:image" content="https://cdn.example.org/different.webp',html)
        self.assertIn('rel="canonical" href="https://shop.example/product/og-y',html)

    def test_uploaded_product_image_is_persisted_in_the_database(self):
        csrf=self.csrf_headers()
        self.assertEqual(self.client.post('/api/admin/login',json={'username':'admin','password':'Long-test-passphrase-2026!'},headers=csrf).status_code,200)
        image_bytes=b'\x89PNG\r\n\x1a\n'+b'test-image-payload'
        data_url='data:image/png;base64,'+base64.b64encode(image_bytes).decode('ascii')
        product={'id':'uploaded-db-image','name':'Product with image','description':'Stored image','images':[data_url]}
        response=self.client.put('/api/products',json={'products':[product]},headers=self.csrf_headers())
        self.assertEqual(response.status_code,200,response.get_data(as_text=True))
        image_url=response.get_json()['products'][0]['images'][0]
        self.assertTrue(image_url.startswith('/uploads/'))
        stored=self.client.get(image_url)
        self.assertEqual(stored.status_code,200)
        self.assertEqual(stored.mimetype,'image/png')
        self.assertEqual(stored.data,image_bytes)
        with closing(sqlite3.connect(app_module.DATABASE_FILE)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM product_images').fetchone()[0],1)

    def test_authentication_password_change_csrf_and_catalog_acl(self):
        self.assertEqual(self.client.put('/api/products', json={'products': []}).status_code, 400)
        csrf = self.csrf_headers()
        login = self.client.post('/api/admin/login', json={'username':'admin','password':'Long-test-passphrase-2026!'}, headers=csrf)
        self.assertEqual(login.status_code, 200)
        self.assertEqual(self.client.put('/api/products', json={'products': []}, headers=self.csrf_headers()).status_code, 200)
        page = self.client.get('/admin/password')
        self.assertEqual(page.status_code, 200)
        token = self.client.get('/api/admin/csrf').get_json()['csrf_token']
        changed = self.client.post('/admin/password', data={'csrf_token':token,'current_password':'Long-test-passphrase-2026!','new_password':'Another-secure-passphrase-2026!','confirm_password':'Another-secure-passphrase-2026!'})
        self.assertEqual(changed.status_code, 302)
        self.assertFalse(self.client.get('/api/admin/session').get_json()['authenticated'])
        with closing(sqlite3.connect(app_module.DATABASE_FILE)) as db:
            stored = db.execute('SELECT password_hash FROM admin_account WHERE id=1').fetchone()[0]
        self.assertNotIn('Another-secure-passphrase-2026!', stored)

    def test_admin_form_login_returns_to_product_dashboard(self):
        self.client.get('/admin')
        with self.client.session_transaction() as browser_session:
            token=browser_session['_csrf']
        response=self.client.post('/admin',data={'csrf_token':token,'username':'admin','password':'Long-test-passphrase-2026!'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(response.headers['Location'],'/#admin')
        session_state=self.client.get('/api/admin/session').get_json()
        self.assertTrue(session_state['authenticated'])
        self.assertEqual(session_state['username'],'admin')

    def test_first_admin_setup_creates_hash_and_opens_dashboard(self):
        with closing(sqlite3.connect(app_module.DATABASE_FILE)) as db, db:
            db.execute('DELETE FROM admin_account')
        self.client.get('/admin/setup')
        with self.client.session_transaction() as browser_session:
            token=browser_session['_csrf']
        response=self.client.post('/admin/setup',data={
            'csrf_token':token,'name':'Store Owner','username':'owner','email':'owner@example.com',
            'password':'A-strong-owner-password-2026!','password2':'A-strong-owner-password-2026!'
        })
        self.assertEqual(response.status_code,302)
        self.assertEqual(response.headers['Location'],'/#admin')
        self.assertEqual(self.client.get('/api/admin/session').get_json()['username'],'owner')
        with closing(sqlite3.connect(app_module.DATABASE_FILE)) as db:
            digest=db.execute('SELECT password_hash FROM admin_account WHERE id=1').fetchone()[0]
        self.assertNotIn('A-strong-owner-password-2026!',digest)

    def test_admin_setup_recovers_existing_primary_account_with_deployment_key(self):
        with patch.dict('os.environ', {'SETUP_KEY':''}):
            self.assertEqual(self.client.get('/admin/setup').status_code,302)
        with patch.dict('os.environ', {'SETUP_KEY':'one-time-recovery-key'}):
            page=self.client.get('/admin/setup')
            self.assertEqual(page.status_code,200)
            self.assertIn('استعادة حساب المدير',page.get_data(as_text=True))
            with self.client.session_transaction() as browser_session:
                token=browser_session['_csrf']
            bad=self.client.post('/admin/setup',data={
                'csrf_token':token,'setup_key':'wrong-key','username':'new-owner',
                'password':'New-owner-password-2026!','password2':'New-owner-password-2026!'
            })
            self.assertEqual(bad.status_code,200)
            with closing(sqlite3.connect(app_module.DATABASE_FILE)) as db:
                self.assertEqual(db.execute('SELECT username FROM admin_account WHERE id=1').fetchone()[0],'admin')
                original_product_count=db.execute('SELECT COUNT(*) FROM products').fetchone()[0]
            recovered=self.client.post('/admin/setup',data={
                'csrf_token':token,'setup_key':'one-time-recovery-key','username':'new-owner',
                'password':'New-owner-password-2026!','password2':'New-owner-password-2026!'
            })
            self.assertEqual(recovered.status_code,302)
            with closing(sqlite3.connect(app_module.DATABASE_FILE)) as db:
                account=db.execute('SELECT username,password_hash FROM admin_account WHERE id=1').fetchone()
                self.assertEqual(db.execute('SELECT COUNT(*) FROM products').fetchone()[0],original_product_count)
            self.assertEqual(account[0],'new-owner')
            self.assertNotIn('New-owner-password-2026!',account[1])

    def test_csrf_required_for_mutation_and_old_product_rows_survive_migration(self):
        self.assertEqual(self.client.post('/api/admin/login', json={'username':'admin','password':'wrong'}).status_code, 400)
        with closing(sqlite3.connect(app_module.DATABASE_FILE)) as db, db:
            db.execute('DROP TABLE products')
            db.execute('CREATE TABLE products(id TEXT PRIMARY KEY,name TEXT NOT NULL,category TEXT NOT NULL,description TEXT NOT NULL,price TEXT NOT NULL,badge TEXT NOT NULL,image TEXT NOT NULL,position INTEGER NOT NULL)')
            db.execute('INSERT INTO products VALUES(?,?,?,?,?,?,?,?)', ('preserved','Existing product','Tech','Keep me','10','','',1))
        app_module.initialize_database()
        product = next(p for p in app_module.load_products() if p['id']=='preserved')
        self.assertEqual(product['description'],'Keep me')

    def test_custom_prefixed_postgres_variable_is_detected_and_runtime_has_no_file_fallback(self):
        with patch.dict('os.environ', {'NEON_CUSTOM_DATABASE_URL':'postgresql://example.invalid/db'}, clear=True):
            self.assertEqual(app_module.resolve_database_url(),'postgresql://example.invalid/db')
        app_module.app.config['TESTING']=False
        try:
            with self.assertRaisesRegex(RuntimeError,'persistent PostgreSQL database is required'):
                with app_module.database_connection():
                    pass
        finally:
            app_module.app.config['TESTING']=True


if __name__ == '__main__': unittest.main()
