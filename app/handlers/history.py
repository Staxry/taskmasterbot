"""
Task history handlers module
Обработчики для просмотра истории изменений задач
"""
from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from app.handlers import core_router
from app.database import get_db_connection
from app.services.users import get_or_create_user
from app.services.task_history import get_task_history, format_history_entry
from app.logging_config import get_logger

logger = get_logger(__name__)


@core_router.callback_query(F.data.startswith("task_history_"))
async def callback_task_history(callback: CallbackQuery):
    """Показать историю изменений задачи"""
    try:
        # Извлекаем task_id из callback_data
        parts = callback.data.split('_')
        if len(parts) < 3:
            logger.error(f"❌ Invalid callback_data format: {callback.data}")
            await callback.answer("❌ Ошибка: неверный формат данных", show_alert=True)
            return
        
        task_id = int(parts[-1])
        
        telegram_id = str(callback.from_user.id)
        username = callback.from_user.username
        first_name = callback.from_user.first_name or ''
        last_name = callback.from_user.last_name or ''
        
        logger.info(f"📜 History for task #{task_id} requested by {username}")
        
        user = get_or_create_user(telegram_id, username, first_name, last_name)
        if not user:
            await callback.answer("❌ Доступ запрещён", show_alert=True)
            return
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # Получаем информацию о задаче
            cur.execute("SELECT id, title FROM tasks WHERE id = ?", (task_id,))
            task = cur.fetchone()
            
            if not task:
                await callback.answer("❌ Задача не найдена", show_alert=True)
                return
            
            # Получаем историю
            history = get_task_history(task_id, limit=20)
            
            text = f"📜 <b>История изменений задачи #{task_id}</b>\n"
            text += f"📋 <b>{task['title']}</b>\n\n"
            
            if not history:
                text += "История изменений пуста."
            else:
                text += "Последние изменения:\n\n"
                for entry in history:
                    text += format_history_entry(entry) + "\n\n"
            
            buttons = [
                [InlineKeyboardButton(text="🔙 К задаче", callback_data=f"task_{task_id}")]
            ]
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
            
            try:
                await callback.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)
            except Exception:
                await callback.message.delete()
                await callback.message.answer(text, parse_mode='HTML', reply_markup=keyboard)
            
            await callback.answer()
            
        finally:
            if 'cur' in locals():
                cur.close()
            if 'conn' in locals():
                conn.close()
                
    except ValueError as e:
        logger.error(f"❌ Error parsing task_id from callback_data '{callback.data}': {e}")
        await callback.answer("❌ Ошибка: неверный ID задачи", show_alert=True)
    except Exception as e:
        logger.error(f"❌ Error in callback_task_history: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при загрузке истории", show_alert=True)

