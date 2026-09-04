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
)

# Read and execute schema
with open('d:\\ForestCare-AI\\forestcare_mysql_schema.sql', 'r', encoding='utf-8') as f:
    schema_content = f.read()

# Split by semicolons and execute each statement
statements = [s.strip() for s in schema_content.split(';') if s.strip()]

cursor = conn.cursor()
for stmt in statements:
    try:
        cursor.execute(stmt)
        print('OK: ' + stmt[:60].replace('\n', ' ')[:60])
    except Exception as e:
        print('ERROR: {}: {}'.format(stmt[:40], str(e)))

conn.commit()
cursor.close()
conn.close()
print('\n=== SCHEMA IMPORT COMPLETE ===')
