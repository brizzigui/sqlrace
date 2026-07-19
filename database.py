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
            title VARCHAR(255) NOT NULL,
            description TEXT NOT NULL,
            init_sql TEXT NOT NULL,
            solution_sql TEXT NOT NULL,
            visibility VARCHAR(20) NOT NULL DEFAULT 'public',
            difficulty INT NOT NULL DEFAULT 1 CHECK (difficulty BETWEEN 1 AND 5),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS contest_questions (
            contest_id INT REFERENCES contests(id) ON DELETE CASCADE,
            question_id INT REFERENCES questions(id) ON DELETE CASCADE,
            PRIMARY KEY (contest_id, question_id)
        );
        """)
        
        cur.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id SERIAL PRIMARY KEY,
            team_id INT REFERENCES teams(id) ON DELETE CASCADE,
            question_id INT REFERENCES questions(id) ON DELETE CASCADE,
            contest_id INT REFERENCES contests(id) ON DELETE CASCADE,
            query TEXT NOT NULL,
            status VARCHAR(50) NOT NULL,
            error_message TEXT,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS contest_participants (
            contest_id INT REFERENCES contests(id) ON DELETE CASCADE,
            team_id INT REFERENCES teams(id) ON DELETE CASCADE,
            entered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (contest_id, team_id)
        );
        """)

        cur.execute("""
        INSERT INTO contest_participants (contest_id, team_id)
        SELECT DISTINCT contest_id, team_id FROM submissions
        WHERE contest_id IS NOT NULL
        ON CONFLICT DO NOTHING;
        """)

        # Migration queries for existing databases
        # 1. Add visibility column to questions if it does not exist
        cur.execute("ALTER TABLE questions ADD COLUMN IF NOT EXISTS visibility VARCHAR(20) NOT NULL DEFAULT 'public';")
        
        # 2. Add difficulty column to questions if it does not exist
        cur.execute("ALTER TABLE questions ADD COLUMN IF NOT EXISTS difficulty INT NOT NULL DEFAULT 1 CHECK (difficulty BETWEEN 1 AND 5);")
        
        # 3. Add contest_id column to submissions if it does not exist
        cur.execute("ALTER TABLE submissions ADD COLUMN IF NOT EXISTS contest_id INT REFERENCES contests(id) ON DELETE CASCADE;")

        # 3. If questions still has contest_id, migrate data to contest_questions and submissions, then drop it
        cur.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='questions' AND column_name='contest_id') THEN
                -- Migrate links to contest_questions
                INSERT INTO contest_questions (contest_id, question_id)
                SELECT contest_id, id FROM questions WHERE contest_id IS NOT NULL
                ON CONFLICT DO NOTHING;

                -- Set contest_id on old submissions
                UPDATE submissions s
                SET contest_id = q.contest_id
                FROM questions q
                WHERE s.question_id = q.id AND s.contest_id IS NULL AND q.contest_id IS NOT NULL;

                -- Drop old column
                ALTER TABLE questions DROP COLUMN contest_id;
            END IF;
        END $$;
        """)

        # Seed default admin if not exists
        admin_username = os.getenv('ADMIN_USERNAME', 'admin')
        admin_password = os.getenv('ADMIN_PASSWORD', 'admin123')
        
        cur.execute("SELECT id FROM teams WHERE username = %s;", (admin_username,))
        if not cur.fetchone():
            hashed_pw = generate_password_hash(admin_password)
            cur.execute("""
            INSERT INTO teams (username, password_hash, is_admin)
            VALUES (%s, %s, TRUE);
            """, (admin_username, hashed_pw))
            print(f"Default admin account created: {admin_username} / {admin_password}")
        
    print("Database tables initialized successfully.")
