import pymysql
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('d:\\ForestCare-AI\\backend\\.env')

# Connect to MySQL
conn = pymysql.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME'),
    cursorclass=pymysql.cursors.DictCursor
)

# Check users table
with conn.cursor() as cursor:
    cursor.execute('SELECT id, email, name FROM users ORDER BY id DESC LIMIT 5')
    users = cursor.fetchall()
    print('Recent users in database:')
    for u in users:
        print('  ID: {}, Email: {}, Name: {}'.format(u['id'], u['email'], u['name']))

# Check diagnosis_history table schema
with conn.cursor() as cursor:
    cursor.execute('DESCRIBE diagnosis_history')
    schema = cursor.fetchall()
    print('\ndiagnosis_history table structure:')
    for col in schema:
        print('  {}: {}'.format(col['Field'], col['Type']))

conn.close()
