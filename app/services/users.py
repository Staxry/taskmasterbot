"""
User service module
Handles user authorization, creation, and management
"""
from typing import Optional, Dict, Any
from app.database import get_db_connection
from app.logging_config import get_logger

logger = get_logger(__name__)


def check_user_authorization(username: str) -> Optional[Dict[str, str]]:
    """
    Проверить, разрешён ли пользователь в системе (whitelist)
    
    Выполняет поиск username в таблице allowed_users для проверки
    авторизации пользователя в системе.
    
    Args:
        username (str): Username пользователя для проверки
        
    Returns:
        Optional[Dict[str, str]]: Словарь с данными {'username': str, 'role': str}
                                  если пользователь авторизован, иначе None
                                  
    Example:
        >>> result = check_user_authorization('ivan_petrov')
        >>> print(result)
        {'username': 'ivan_petrov', 'role': 'admin'}
    """
    if not username:
        logger.warning("⚠️ [check_user_authorization] Empty username provided")
        return None
    
    logger.info(f"🔍 [check_user_authorization] Checking authorization for username: {username}")
    
    conn = None
    cur = None
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        logger.debug(f"📊 [check_user_authorization] Querying allowed_users table for: {username}")
        
        cur.execute(
            "SELECT username, role FROM allowed_users WHERE username = ?",
            (username,)
        )
        result = cur.fetchone()
        
        if result:
            user_data = {'username': result['username'], 'role': result['role']}
            logger.info(f"✅ [check_user_authorization] User {username} is authorized with role: {result['role']}")
            return user_data
        else:
            logger.warning(f"❌ [check_user_authorization] User {username} not found in whitelist")
            return None
            
    except Exception as e:
        logger.error(f"❌ [check_user_authorization] Database error while checking user {username}: {e}", exc_info=True)
        return None
        
    finally:
        if cur:
            cur.close()
            logger.debug(f"🔌 [check_user_authorization] Database cursor closed")
        if conn:
            conn.close()
            logger.debug(f"🔌 [check_user_authorization] Database connection closed")


def get_or_create_user(telegram_id: str, username: str, first_name: str) -> Optional[Dict[str, Any]]:
    """
    Получить существующего пользователя или создать нового (только если в whitelist)
    
    Функция выполняет следующие действия:
    1. Проверяет наличие username в whitelist (allowed_users)
    2. Если пользователя нет в whitelist - возвращает None
    3. Ищет пользователя по telegram_id в таблице users
    4. Если пользователь существует - обновляет роль при необходимости
    5. Если пользователя нет - создаёт нового с ролью из whitelist
    
    Args:
        telegram_id (str): Telegram ID пользователя
        username (str): Username пользователя (без @)
        first_name (str): Имя пользователя
        
    Returns:
        Optional[Dict[str, Any]]: Словарь с данными пользователя:
                                  {'id': int, 'telegram_id': str, 'username': str, 'role': str}
                                  или None если пользователь не авторизован
                                  
    Example:
        >>> user = get_or_create_user('123456789', 'ivan_petrov', 'Ivan')
        >>> print(user)
        {'id': 1, 'telegram_id': '123456789', 'username': 'ivan_petrov', 'role': 'admin'}
    """
    if not username:
        logger.warning(f"⚠️ [get_or_create_user] Empty username provided for telegram_id: {telegram_id}")
        return None
    
    logger.info(f"🔍 [get_or_create_user] Processing user: telegram_id={telegram_id}, username={username}, first_name={first_name}")
    
    allowed = check_user_authorization(username)
    if not allowed:
        logger.warning(f"❌ [get_or_create_user] User {username} is not in whitelist, access denied")
        return None
    
    logger.info(f"✅ [get_or_create_user] User {username} is authorized as {allowed['role']}")
    
    conn = None
    cur = None
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        logger.debug(f"📊 [get_or_create_user] Searching for existing user with telegram_id: {telegram_id}")
        
        cur.execute(
            "SELECT id, telegram_id, username, role FROM users WHERE telegram_id = ?",
            (telegram_id,)
        )
        user = cur.fetchone()
        
        if user:
            logger.info(f"👤 [get_or_create_user] Found existing user: id={user['id']}, username={user['username']}, role={user['role']}")
            
            if user['role'] != allowed['role']:
                logger.info(f"🔄 [get_or_create_user] Role mismatch detected. Updating role from {user['role']} to {allowed['role']}")
                
                cur.execute(
                    "UPDATE users SET role = ? WHERE telegram_id = ?",
                    (allowed['role'], telegram_id)
                )
                conn.commit()
                
                logger.info(f"✅ [get_or_create_user] Successfully updated role for {username}: {allowed['role']}")
            else:
                logger.debug(f"ℹ️ [get_or_create_user] Role unchanged for {username}: {user['role']}")
            
            user_data = {
                'id': user['id'],
                'telegram_id': user['telegram_id'],
                'username': user['username'],
                'role': allowed['role']
            }
            
            logger.info(f"✅ [get_or_create_user] Returning existing user data: {user_data}")
            return user_data
            
        else:
            logger.info(f"➕ [get_or_create_user] User not found, creating new user: {username}")
            
            cur.execute(
                """INSERT INTO users (telegram_id, username, role, created_at, updated_at) 
                   VALUES (?, ?, ?, datetime('now'), datetime('now'))""",
                (telegram_id, username, allowed['role'])
            )
            conn.commit()
            new_user_id = cur.lastrowid
            
            # Получаем созданного пользователя
            cur.execute(
                "SELECT id, telegram_id, username, role FROM users WHERE id = ?",
                (new_user_id,)
            )
            new_user = cur.fetchone()
            
            user_data = {
                'id': new_user['id'],
                'telegram_id': new_user['telegram_id'],
                'username': new_user['username'],
                'role': new_user['role']
            }
            
            logger.info(f"✅ [get_or_create_user] Successfully created new user: {username} as {allowed['role']}, id={new_user['id']}")
            logger.debug(f"📊 [get_or_create_user] New user data: {user_data}")
            
            return user_data
            
    except Exception as e:
        logger.error(f"❌ [get_or_create_user] Database error while processing user {username}: {e}", exc_info=True)
        
        if conn:
            try:
                conn.rollback()
                logger.warning(f"🔄 [get_or_create_user] Transaction rolled back due to error")
            except Exception as rollback_error:
                logger.error(f"❌ [get_or_create_user] Rollback failed: {rollback_error}", exc_info=True)
        
        return None
        
    finally:
        if cur:
            cur.close()
            logger.debug(f"🔌 [get_or_create_user] Database cursor closed")
        if conn:
            conn.close()
            logger.debug(f"🔌 [get_or_create_user] Database connection closed")
