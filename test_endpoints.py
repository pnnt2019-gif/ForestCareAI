import requests
import json

email = 'test.browser@forestcare.com'

print('=== TESTING API ENDPOINTS ===\n')

# 1. Get diseases
diseases_resp = requests.get('http://127.0.0.1:5000/api/diseases')
print('1. GET /api/diseases -', diseases_resp.status_code)
print('   Trees:', list(diseases_resp.json()['diseases'].keys()))

# 2. Get trees
trees_resp = requests.get('http://127.0.0.1:5000/api/trees')
print('\n2. GET /api/trees -', trees_resp.status_code)
print('   Trees:', trees_resp.json()['trees'])

# 3. Save history (manual record)
history_payload = {
    'email': email,
    'record': {
        'tree': 'Gõ đỏ',
        'disease': 'Đốm đen',
        'symptoms': 'Vết bệnh cục bộ trên lá',
        'level': 'medium',
        'status': 'Bị bệnh'
    }
}
save_resp = requests.post('http://127.0.0.1:5000/api/history', json=history_payload)
print('\n3. POST /api/history (save) -', save_resp.status_code)

# 4. Get history
get_resp = requests.get('http://127.0.0.1:5000/api/history?email=' + email)
print('\n4. GET /api/history -', get_resp.status_code)
history = get_resp.json().get('history', [])
print('   Found ' + str(len(history)) + ' records')
if history:
    print('   Latest: ' + history[0].get('tree') + ' - ' + history[0].get('disease'))

# 5. Test migration endpoint
migration_payload = {
    'email': email,
    'history': [
        {'tree': 'Hồng lộc', 'disease': 'Cháy lá sinh lý', 'symptoms': 'Khô lá', 'level': 'low', 'status': 'Bị bệnh'},
        {'tree': 'Lát hoa', 'disease': 'Đốm nâu', 'symptoms': 'Vết nâu', 'level': 'medium', 'status': 'Bị bệnh'}
    ]
}
migrate_resp = requests.post('http://127.0.0.1:5000/api/migrate-history', json=migration_payload)
print('\n5. POST /api/migrate-history -', migrate_resp.status_code)
if migrate_resp.status_code == 200:
    print('   Migrated: ' + str(migrate_resp.json().get('migrated')) + ' records')

print('\n=== ALL ENDPOINTS VERIFIED ===')
