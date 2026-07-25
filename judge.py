import time
import uuid
import psycopg2
from database import sandbox_pool, init_pools

def evaluate_submission(init_sql, solution_sql, user_query):
    """
    Evaluates a user-submitted SQL query against a reference solution.
    
    1. Creates a unique temporary schema in the sandbox database.
    2. Runs init_sql to create the schema state and insert mock data.
    3. Runs solution_sql to get expected column headers and rows.
    4. Runs user_query to get actual column headers and rows.
    5. Rollbacks the transaction to automatically wipe the schema.
    6. Compares columns and row contents (order-sensitive if ORDER BY is in the solution).
    
    Returns:
        (status, error_message, user_cols, user_rows, exec_time_ms)
    """
    start_time = time.time()
    schema_name = f"sandbox_{uuid.uuid4().hex}"
    
    init_pools()
    conn = sandbox_pool.getconn()
    conn.autocommit = False
    
    status = "Pending"
    error_message = None
    user_cols = []
    user_rows = []
    
    try:
        cur = conn.cursor()
        
        # Set up a sandbox schema for this transaction
        cur.execute(f"CREATE SCHEMA {schema_name};")
        cur.execute(f"SET search_path TO {schema_name};")
        
        # Enforce statement timeout to prevent denial-of-service / hanging queries
        cur.execute("SET local statement_timeout = 2000; -- 2 seconds timeout")
        
        # Execute initialization script
        try:
            cur.execute(init_sql)
        except Exception as e:
            status = "Runtime Error"
            error_message = f"Setup Error (init_sql failed): {str(e)}"
            exec_time_ms = int((time.time() - start_time) * 1000)
            return status, error_message, [], [], exec_time_ms
            
        # Execute reference solution
        try:
            cur.execute(solution_sql)
            sol_cols = [desc[0].lower() for desc in cur.description] if cur.description else []
            sol_rows = cur.fetchall()
        except Exception as e:
            status = "Runtime Error"
            error_message = f"Setup Error (solution_sql failed): {str(e)}"
            exec_time_ms = int((time.time() - start_time) * 1000)
            return status, error_message, [], [], exec_time_ms
            
        # Execute user query
        try:
            cur.execute(user_query)
            user_cols = [desc[0].lower() for desc in cur.description] if cur.description else []
            user_rows = cur.fetchall()
        except Exception as e:
            status = "Runtime Error"
            error_message = str(e)
            exec_time_ms = int((time.time() - start_time) * 1000)
            return status, error_message, [], [], exec_time_ms
            
        # Compare columns count
        if len(sol_cols) != len(user_cols):
            status = "Wrong Answer"
            error_message = f"Column count mismatch. Expected {len(sol_cols)}, got {len(user_cols)}."
            exec_time_ms = int((time.time() - start_time) * 1000)
            return status, error_message, user_cols, user_rows, exec_time_ms
            
        # Compare columns names in order
        for idx, (sc, uc) in enumerate(zip(sol_cols, user_cols)):
            if sc != uc:
                status = "Wrong Answer"
                error_message = f"Column name mismatch at position {idx+1}. Expected '{sc}', got '{uc}'."
                exec_time_ms = int((time.time() - start_time) * 1000)
                return status, error_message, user_cols, user_rows, exec_time_ms
                
        # Compare rows count
        if len(sol_rows) != len(user_rows):
            status = "Wrong Answer"
            error_message = f"Row count mismatch. Expected {len(sol_rows)} rows, got {len(user_rows)} rows."
            exec_time_ms = int((time.time() - start_time) * 1000)
            return status, error_message, user_cols, user_rows, exec_time_ms
            
        # Check if solution enforces sorting order
        is_ordered = "order by" in solution_sql.lower()
        
        if is_ordered:
            # Order-sensitive comparison
            for idx, (s_row, u_row) in enumerate(zip(sol_rows, user_rows)):
                if s_row != u_row:
                    status = "Wrong Answer"
                    error_message = f"Row comparison mismatch at index {idx+1}."
                    exec_time_ms = int((time.time() - start_time) * 1000)
                    return status, error_message, user_cols, user_rows, exec_time_ms
        else:
            # Order-insensitive comparison: sort rows in Python
            def sort_key(row):
                return tuple(str(val) if val is not None else '' for val in row)
                
            try:
                sorted_sol = sorted(sol_rows, key=sort_key)
                sorted_usr = sorted(user_rows, key=sort_key)
            except Exception:
                # Fallback simple string comparison if complex structures can't be tupled
                sorted_sol = sorted(list(map(str, sol_rows)))
                sorted_usr = sorted(list(map(str, user_rows)))
                
            if sorted_sol != sorted_usr:
                status = "Wrong Answer"
                error_message = "Rows content mismatch (query returned correct columns but different rows)."
                exec_time_ms = int((time.time() - start_time) * 1000)
                return status, error_message, user_cols, user_rows, exec_time_ms
                
        # If all checks pass
        status = "Accepted"
        
    except Exception as e:
        status = "Runtime Error"
        error_message = f"System Error: {str(e)}"
    finally:
        # Rollback transaction to automatically drop the created schema and free up pool connection
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
            sandbox_pool.putconn(conn)
            
    exec_time_ms = int((time.time() - start_time) * 1000)
    return status, error_message, user_cols, user_rows, exec_time_ms

