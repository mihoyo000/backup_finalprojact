# ---------- 테이블명 확인 ---------- #
# import sqlite3

# conn = sqlite3.connect("db.sqlite3")
# cursor = conn.cursor()

# # 데이터베이스에 있는 모든 테이블 이름 확인
# cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
# tables = cursor.fetchall()

# print("🔍 테이블 목록:")
# for table in tables:
#     print(table[0])

# conn.close()


# ---------- 테이블명 확인 후 ---------- #
import sqlite3

conn = sqlite3.connect("db.sqlite3")
cursor = conn.cursor()

# 해당 테이블에서 모든 데이터 조회
cursor.execute("SELECT * FROM flo_category;")  # FROM 뒤에 원하는 테이블명 입력
rows = cursor.fetchall()

print("📦 카테고리 목록:")
for row in rows:
    print(row)
    
cursor.execute("PRAGMA table_info(flo_category);")  # info() 안에 조회했던 테이블명 입력
print("📌 컬럼 정보:")
for col in cursor.fetchall():
    print(col)

conn.close()