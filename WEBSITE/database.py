import sqlite3
import bcrypt
from pathlib import Path
from datetime import datetime

DB_PATH = Path("users.db")

def init_db():
    """Inicializa o banco de dados e cria a tabela de usuários."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                is_admin BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Criar um administrador padrão, se não existir
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1")
        if cursor.fetchone()[0] == 0:
            hashed_password = bcrypt.hashpw("admin123".encode('utf-8'), bcrypt.gensalt())
            cursor.execute(
                "INSERT OR IGNORE INTO users (name, email, password, is_admin) VALUES (?, ?, ?, ?)",
                ("Admin", "admin@example.com", hashed_password, 1)
            )
        conn.commit()

def register_user(name: str, email: str, password: str, is_admin: bool = False) -> bool:
    """Registra um novo usuário com senha hasheada."""
    try:
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (name, email, password, is_admin) VALUES (?, ?, ?, ?)",
                (name, email, hashed_password, is_admin)
            )
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # E-mail já existe
    except Exception as e:
        print(f"Erro ao registrar: {e}")
        return False

def authenticate_user(email: str, password: str) -> bool:
    """Verifica as credenciais do usuário."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT password FROM users WHERE email = ?", (email,))
            result = cursor.fetchone()
            if result:
                stored_password = result[0]
                return bcrypt.checkpw(password.encode('utf-8'), stored_password)
        return False
    except Exception as e:
        print(f"Erro ao autenticar: {e}")
        return False

def get_user_name(email: str) -> str:
    """Obtém o nome do usuário pelo e-mail."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM users WHERE email = ?", (email,))
            result = cursor.fetchone()
            return result[0] if result else ""
    except Exception as e:
        print(f"Erro ao obter nome: {e}")
        return ""

def is_admin(email: str) -> bool:
    """Verifica se o usuário é administrador."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT is_admin FROM users WHERE email = ?", (email,))
            result = cursor.fetchone()
            return result[0] == 1 if result else False
    except Exception as e:
        print(f"Erro ao verificar admin: {e}")
        return False

def get_all_users() -> list:
    """Retorna todos os usuários do banco."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name, email, created_at, is_admin FROM users")
            return [
                {"name": row[0], "email": row[1], "created_at": row[2], "is_admin": bool(row[3])}
                for row in cursor.fetchall()
            ]
    except Exception as e:
        print(f"Erro ao listar usuários: {e}")
        return []