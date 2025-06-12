import sqlite3

# 1. 백업 DB 경로
backup_db_path = "C:/Users/Admin/Desktop/category_backup/db.sqlite3"  # 실제 경로로 수정하세요
current_db_path = "db.sqlite3"  # 현재 프로젝트 DB

# 2. 백업 DB에서 데이터 읽기
backup_conn = sqlite3.connect(backup_db_path)
backup_cursor = backup_conn.cursor()
backup_cursor.execute("SELECT id, name, slug, parent_id FROM flo_category")
category_data = backup_cursor.fetchall()
backup_conn.close()

# 3. 현재 DB에 데이터 삽입
current_conn = sqlite3.connect(current_db_path)
current_cursor = current_conn.cursor()

# 선택 사항: 기존 카테고리 삭제 (원하는 경우에만!)
# current_cursor.execute("DELETE FROM flo_category")

# 중복 방지: 이미 있는 id는 skip하거나 REPLACE INTO 사용
for row in category_data:
    current_cursor.execute("""
        INSERT OR IGNORE INTO flo_category (id, name, slug, parent_id)
        VALUES (?, ?, ?, ?)
    """, row)

current_conn.commit()
current_conn.close()

print(f"✅ {len(category_data)}개 카테고리 항목을 성공적으로 가져왔습니다.")
