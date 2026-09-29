import base64
import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path

import app as app_module


class ProductSharingTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.original_database_file = app_module.DATABASE_FILE
        self.original_instance_path = app_module.app.instance_path
        app_module.DATABASE_FILE = Path(self.temporary_directory.name) / 'tech_house.db'
        app_module.app.instance_path = self.temporary_directory.name
        app_module.initialize_database()
        self.client = app_module.app.test_client()
        self.client.post('/api/admin/login', json={'username': 'admin', 'password': '123456'})

    def tearDown(self):
        app_module.DATABASE_FILE = self.original_database_file
        app_module.app.instance_path = self.original_instance_path
        self.temporary_directory.cleanup()

    def test_new_product_has_server_rendered_share_page(self):
        product = {
            'id': 'new-share-product',
            'name': 'New share product',
            'category': 'أجهزة',
            'price': 'LE 100',
            'description': 'Product page description',
            'specs': ['Test specification'],
            'images': ['https://example.com/product.jpg']
        }

        response = self.client.put('/api/products', json={'products': [product]})
        self.assertEqual(response.status_code, 200)

        page = self.client.get('/product/new-share-product')
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'New share product |', page.data)
        self.assertIn(b'og:image', page.data)
        self.assertEqual(self.client.get('/product/cam-05').status_code, 404)

        with closing(sqlite3.connect(app_module.DATABASE_FILE)) as connection:
            saved_product = connection.execute(
                'SELECT id, name FROM products WHERE id = ?', ('new-share-product',)
            ).fetchone()
        self.assertEqual(saved_product, ('new-share-product', 'New share product'))

    def test_uploaded_product_image_gets_a_public_url(self):
        image = base64.b64encode(b'product-image').decode('ascii')
        product = {
            'id': 'image-share-product',
            'name': 'Image share product',
            'price': 'LE 10',
            'description': 'Uploaded image test',
            'specs': [],
            'images': [f'data:image/png;base64,{image}']
        }

        response = self.client.put('/api/products', json={'products': [product]})
        self.assertEqual(response.status_code, 200)
        image_url = response.get_json()['products'][0]['images'][0]
        self.assertTrue(image_url.startswith('/uploads/'))
        image_response = self.client.get(image_url)
        self.assertEqual(image_response.status_code, 200)
        image_response.close()

    def test_numeric_product_id_is_normalized_and_resolves(self):
        product = {
            'id': 42,
            'name': 'Legacy numeric ID product',
            'price': 'LE 10',
            'description': 'Numeric ID detail test',
            'specs': [],
            'images': ['https://example.com/product.jpg']
        }

        response = self.client.put('/api/products', json={'products': [product]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['products'][0]['id'], '42')
        self.assertEqual(self.client.get('/product/42').status_code, 200)

    def test_existing_sqlite_product_row_survives_schema_migration(self):
        with closing(sqlite3.connect(app_module.DATABASE_FILE)) as connection:
            connection.execute('DROP TABLE products')
            connection.execute('''
                CREATE TABLE products (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    description TEXT NOT NULL,
                    price TEXT NOT NULL,
                    badge TEXT NOT NULL,
                    image TEXT NOT NULL,
                    position INTEGER NOT NULL
                )
            ''')
            connection.execute(
                'INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                ('existing-row', 'Existing item', 'Accessories', 'Keep this row', '10', 'Old', '', 1)
            )
            connection.commit()

        app_module.initialize_database()
        migrated_product = next(
            product for product in app_module.load_products() if product['id'] == 'existing-row'
        )
        self.assertEqual(migrated_product['name'], 'Existing item')
        self.assertEqual(migrated_product['description'], 'Keep this row')
        with closing(sqlite3.connect(app_module.DATABASE_FILE)) as connection:
            columns = {row[1] for row in connection.execute('PRAGMA table_info(products)')}
        self.assertTrue({'old_price', 'specs_json', 'images_json'}.issubset(columns))

    def test_product_catalog_cannot_be_changed_without_admin_login(self):
        anonymous_client = app_module.app.test_client()
        session_response = anonymous_client.get('/api/admin/session')
        self.assertFalse(session_response.get_json()['authenticated'])
        response = anonymous_client.put('/api/products', json={'products': []})
        self.assertEqual(response.status_code, 401)


if __name__ == '__main__':
    unittest.main()