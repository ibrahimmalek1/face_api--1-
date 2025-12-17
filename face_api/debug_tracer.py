import mysql.connector
import sys

print("🕵️ STARTING DATA TRACER...")

config = {
    "host": "127.0.0.1",   # Force IPv4
    "user": "root",
    "password": "",        # Leave empty if you have no password
    "database": "face_db",
    "port": 3306
}

try:
    # 1. Connect
    conn = mysql.connector.connect(**config)
    cursor = conn.cursor()
    print("✅ Connected to MySQL (127.0.0.1)")

    # 2. Check Table Structure
    cursor.execute("DESCRIBE faces")
    columns = [row[0] for row in cursor.fetchall()]
    print(f"✅ Found table 'faces' with columns: {columns}")

    # 3. FORCE INSERT (The Acid Test)
    # We deliberately insert dummy data to see if it sticks.
    print("\nAttempting to insert test row...")
    insert_sql = "INSERT INTO faces (image_path, s3_url) VALUES ('DEBUG_TEST_IMAGE', 'http://debug.com')"
    cursor.execute(insert_sql)
    conn.commit()  # <--- CRITICAL STEP
    print("✅ Insert executed and COMMITTED.")

    # 4. READ BACK IMMEDIATELY
    print("\nReading back data...")
    cursor.execute("SELECT * FROM faces WHERE image_path='DEBUG_TEST_IMAGE'")
    row = cursor.fetchone()

    if row:
        print(f"🎉 SUCCESS! Found the row we just added. ID: {row[0]}")
        print("Conclusion: Your database works perfectly.")
        print("ACTION: Go to phpMyAdmin, click 'face_db', then 'faces', and look for 'DEBUG_TEST_IMAGE'.")
    else:
        print("❌ FAILURE: Inserted row vanished immediately.")
        print("Possible causes: Transaction rollback, triggers, or strict mode.")

except mysql.connector.Error as err:
    print(f"\n❌ MYSQL ERROR: {err}")
except Exception as e:
    print(f"\n❌ PYTHON ERROR: {e}")
finally:
    if 'conn' in locals() and conn.is_connected():
        cursor.close()
        conn.close()
        print("\nConnection closed.")