import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "../smart112.db")
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("DELETE FROM incidents")
    c.execute("DELETE FROM dispatch_assignments")
    c.execute("DELETE FROM audit_logs")
    c.execute("UPDATE emergency_units SET status = 'AVAILABLE'")
    conn.commit()
    inc_count = c.execute("SELECT count(*) FROM incidents").fetchone()[0]
    units_avail = c.execute("SELECT count(*) FROM emergency_units WHERE status = 'AVAILABLE'").fetchone()[0]
    conn.close()
    print(f"Database reset successful. Incidents: {inc_count}, Available Units: {units_avail}")
else:
    print("Database file does not exist yet. It will be initialized cleanly on server startup.")

