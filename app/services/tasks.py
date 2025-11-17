"""
Task service module
Вспомогательные функции для работы с задачами

Этот модуль содержит служебные функции для управления задачами,
их статусами, приоритетами и взаимодействием с базой данных.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.database import get_db_connection
from app.logging_config import get_logger

logger = get_logger(__name__)
