"""
Database connection and query functions for the Lost & Found Portal
"""

import time
import mysql.connector
from werkzeug.security import generate_password_hash
from config import DB_CONFIG, ADMIN_PASSWORD, SESSION_TIMEOUT


def get_db():
    """
    Create and return a MySQL database connection
    Autocommit is enabled to reduce lock hold times
    """
    con = mysql.connector.connect(**DB_CONFIG)
    con.autocommit = True
    return con


def query_db(query, args=(), fetchone=False, commit=False, return_id=False, retries=3):
    """
    Execute a database query with automatic retry logic for lock timeouts
    
    Args:
        query: SQL query string
        args: Tuple of query parameters
        fetchone: If True, return single row; if False, return all rows
        commit: If True, commit the transaction
        return_id: If True, return the last inserted ID
        retries: Number of retry attempts for lock timeouts
    
    Returns:
        Query result or last inserted ID
    """
    last_error = None
    for attempt in range(retries):
        con = get_db()
        cur = con.cursor(dictionary=True)
        try:
            cur.execute(query, args)
            if commit:
                con.commit()
            if return_id:
                id_val = cur.lastrowid
                cur.close()
                con.close()
                return id_val
            result = cur.fetchone() if fetchone else cur.fetchall()
            cur.close()
            con.close()
            return result
        except mysql.connector.errors.DatabaseError as e:
            cur.close()
            con.close()
            if e.errno == 1205 and attempt < retries - 1:  # Lock timeout
                wait_time = 0.1 * (2 ** attempt)  # Exponential backoff
                time.sleep(wait_time)
                last_error = e
                continue
            raise e
    raise last_error


def init_db():
    """
    Initialize database tables and create default admin user
    """
    # Set session lock timeout
    con = get_db()
    cur = con.cursor()
    cur.execute(f"SET SESSION innodb_lock_wait_timeout = {SESSION_TIMEOUT}")
    con.commit()
    cur.close()
    con.close()
    
    # Create users table
    query_db("""CREATE TABLE IF NOT EXISTS users(
            id INT AUTO_INCREMENT PRIMARY KEY,
            email VARCHAR(255) UNIQUE,
            first_name VARCHAR(100),
            last_name VARCHAR(100),
            password VARCHAR(255)
        )""", commit=True)
    
    # Create items table
    query_db("""CREATE TABLE IF NOT EXISTS items(
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_email VARCHAR(255),
            type VARCHAR(20),
            item_name VARCHAR(255),
            description TEXT,
            location VARCHAR(255),
            image_urls TEXT,
            phone VARCHAR(20),
            status VARCHAR(20) DEFAULT 'pending'
        )""", commit=True)
    
    # Create admin table
    query_db("""CREATE TABLE IF NOT EXISTS admin(
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) UNIQUE,
            password VARCHAR(255)
        )""", commit=True)
    
    # Create notifications table
    query_db("""CREATE TABLE IF NOT EXISTS notifications(
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_email VARCHAR(255),
            message TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""", commit=True)
    
    # Create matches table
    query_db("""CREATE TABLE IF NOT EXISTS matches(
            id INT AUTO_INCREMENT PRIMARY KEY,
            lost_item_id INT,
            found_item_id INT,
            lost_email VARCHAR(255),
            found_email VARCHAR(255),
            status VARCHAR(20) DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lost_item_id) REFERENCES items(id),
            FOREIGN KEY (found_item_id) REFERENCES items(id)
        )""", commit=True)
    
    # Alter matches table to ensure VARCHAR status
    try:
        query_db("ALTER TABLE matches MODIFY COLUMN status VARCHAR(20) DEFAULT 'pending'", commit=True)
    except mysql.connector.errors.ProgrammingError:
        pass
    
    # Migrate old image column to image_urls
    try:
        query_db("ALTER TABLE items ADD COLUMN image_urls TEXT AFTER image", commit=True)
        query_db("""
            UPDATE items
            SET image_urls = JSON_ARRAY(image)
            WHERE image IS NOT NULL AND image != ''
        """, commit=True)
        query_db("ALTER TABLE items DROP COLUMN image", commit=True)
    except mysql.connector.errors.ProgrammingError:
        pass
    
    # Add phone column if not exists
    try:
        query_db("ALTER TABLE items ADD COLUMN phone VARCHAR(20)", commit=True)
    except mysql.connector.errors.ProgrammingError:
        pass
    
    # Create default admin user if not exists
    con = get_db()
    cur = con.cursor(dictionary=True)
    cur.execute("SELECT * FROM admin WHERE username=%s", ("admin",))
    row = cur.fetchone()
    if not row:
        hashed = generate_password_hash(ADMIN_PASSWORD)
        cur2 = con.cursor()
        cur2.execute("INSERT INTO admin (username, password) VALUES (%s, %s)", ("admin", hashed))
        con.commit()
        cur2.close()
    cur.close()
    con.close()
