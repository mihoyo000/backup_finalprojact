import sqlite3

conn = sqlite3.connect("db.sqlite3")
cursor = conn.cursor()

# flo_category 테이블에서 모든 데이터 조회
cursor.execute("SELECT * FROM flo_category;")
rows = cursor.fetchall()

print("📦 카테고리 목록:")
for row in rows:
    print(row)
    
cursor.execute("PRAGMA table_info(flo_category);")
print("📌 컬럼 정보:")
for col in cursor.fetchall():
    print(col)


conn.close()