import os
from contextlib import contextmanager
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

load_dotenv()

main_pool = None
sandbox_pool = None

def init_pools():
    global main_pool, sandbox_pool
    if main_pool is None:
        main_pool = ThreadedConnectionPool(
            1, 20,
            host=os.getenv("DB_MAIN_HOST", "localhost"),
            port=int(os.getenv("DB_MAIN_PORT", 5432)),
            database=os.getenv("DB_MAIN_NAME", "sqlrace_main"),
            user=os.getenv("DB_MAIN_USER", "postgres"),
            password=os.getenv("DB_MAIN_PASSWORD", "mainpassword")
        )
    if sandbox_pool is None:
        sandbox_pool = ThreadedConnectionPool(
            1, 20,
            host=os.getenv("DB_SANDBOX_HOST", "localhost"),
            port=int(os.getenv("DB_SANDBOX_PORT", 5433)),
            database=os.getenv("DB_SANDBOX_NAME", "sqlrace_sandbox"),
            user=os.getenv("DB_SANDBOX_USER", "postgres"),
            password=os.getenv("DB_SANDBOX_PASSWORD", "sandboxpassword")
        )

@contextmanager
def get_main_db(cursor_factory=None):
    init_pools()
    conn = main_pool.getconn()
    try:
        cur = conn.cursor(cursor_factory=cursor_factory)
        yield cur
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        main_pool.putconn(conn)

@contextmanager
def get_sandbox_db(cursor_factory=None):
    init_pools()
    conn = sandbox_pool.getconn()
    try:
        cur = conn.cursor(cursor_factory=cursor_factory)
        yield cur
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        sandbox_pool.putconn(conn)

def init_db():
    init_pools()
    # Main Database Schema
    with get_main_db() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            id SERIAL PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            is_admin BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        
        cur.execute("""
        CREATE TABLE IF NOT EXISTS contests (
            id SERIAL PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            description TEXT,
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        
        cur.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id SERIAL PRIMARY KEY,
            contest_id INT REFERENCES contests(id) ON DELETE CASCADE,
            title VARCHAR(255) NOT NULL,
            description TEXT NOT NULL,
            init_sql TEXT NOT NULL,
            solution_sql TEXT NOT NULL,
            points INT DEFAULT 100,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        
        cur.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id SERIAL PRIMARY KEY,
            team_id INT REFERENCES teams(id) ON DELETE CASCADE,
            question_id INT REFERENCES questions(id) ON DELETE CASCADE,
            query TEXT NOT NULL,
            status VARCHAR(50) NOT NULL,
            error_message TEXT,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Seed default admin if not exists
        cur.execute("SELECT id FROM teams WHERE username = 'admin';")
        if not cur.fetchone():
            hashed_pw = generate_password_hash("admin123")
            cur.execute("""
            INSERT INTO teams (username, password_hash, is_admin)
            VALUES ('admin', %s, TRUE);
            """, (hashed_pw,))
            print("Default admin account created: admin / admin123")
        
    print("Database tables initialized successfully.")
