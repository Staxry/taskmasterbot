"""
Comments handlers module
Обработчики для работы с комментариями к задачам
"""
from aiogram import F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from app.handlers import core_router
from app.database import get_db_connection
from app.services.users import get_or_create_user
from app.services.comments import add_comment, get_task_comments, add_comment_file, notify_mentioned_users
from app.services.task_history import add_task_history_entry
from app.keyboards.main_menu import get_main_keyboard
from app.keyboards.task_keyboards import is_mobile_device
from app.states import CommentStates
from app.logging_config import get_logger
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = get_logger(__name__)


@core_router.callback_query(F.data.startswith("task_comments_"))
async def callback_task_comments(callback: CallbackQuery):
    """Показать комментарии к задаче"""
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
        
        logger.info(f"💬 Comments for task #{task_id} requested by {username}")
        
        user = get_or_create_user(telegram_id, username, first_name, last_name)
        if not user:
            await callback.answer("❌ Доступ запрещён", show_alert=True)
            return
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # Получаем информацию о задаче
            cur.execute("SELECT id, title, status, assigned_to_id FROM tasks WHERE id = ?", (task_id,))
            task = cur.fetchone()
            
            if not task:
                await callback.answer("❌ Задача не найдена", show_alert=True)
                return
            
            # Получаем комментарии
            comments = get_task_comments(task_id)
            
            text = f"💬 <b>Комментарии к задаче #{task_id}</b>\n"
            text += f"📋 <b>{task['title']}</b>\n\n"
            
            if not comments:
                text += "Пока нет комментариев.\n\nНажмите кнопку ниже, чтобы добавить комментарий."
            else:
                for comment in comments:
                    author_username = comment.get('username', 'Неизвестно')
                    author_first_name = comment.get('first_name')
                    author_last_name = comment.get('last_name')
                    comment_text = comment['comment_text']
                    created_at = comment.get('created_at')
                    
                    # Форматируем имя автора
                    if author_first_name or author_last_name:
                        author_display = f"{author_first_name or ''} {author_last_name or ''}".strip() + f" (@{author_username})"
                    else:
                        author_display = f"@{author_username}"
                    
                    # Форматируем дату
                    if isinstance(created_at, str):
                        date_str = created_at[:16].replace('T', ' ')
                    else:
                        date_str = str(created_at)[:16]
                    
                    text += f"👤 <b>{author_display}</b>\n"
                    text += f"📅 {date_str}\n"
                    text += f"💬 {comment_text}\n"
                    
                    # Показываем упоминания
                    if comment.get('mentions'):
                        mentions_text = ", ".join([f"@{m['username']}" for m in comment['mentions']])
                        text += f"🔔 Упомянуты: {mentions_text}\n"
                    
                    # Показываем файлы
                    if comment.get('files'):
                        file_count = len(comment['files'])
                        text += f"📎 Файлов: {file_count}\n"
                    
                    text += "\n" + "─" * 30 + "\n\n"
            
            buttons = [
                [InlineKeyboardButton(text="➕ Добавить комментарий", callback_data=f"add_comment_{task_id}")],
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
        logger.error(f"❌ Error in callback_task_comments: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при загрузке комментариев", show_alert=True)


@core_router.callback_query(F.data.startswith("add_comment_"))
async def callback_add_comment(callback: CallbackQuery, state: FSMContext):
    """Начать добавление комментария"""
    task_id = int(callback.data.split('_')[-1])
    
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    last_name = callback.from_user.last_name or ''
    
    logger.info(f"➕ Add comment to task #{task_id} by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    await state.update_data(task_id=task_id)
    await state.set_state(CommentStates.waiting_for_comment_text)
    
    cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])
    
    text = (
        f"💬 <b>Добавить комментарий к задаче #{task_id}</b>\n\n"
        f"Напишите ваш комментарий:\n\n"
        f"💡 <i>Вы можете упомянуть пользователей, используя @username</i>"
    )
    
    try:
        await callback.message.edit_text(text, parse_mode='HTML', reply_markup=cancel_keyboard)
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, parse_mode='HTML', reply_markup=cancel_keyboard)
    
    await callback.answer()


@core_router.message(CommentStates.waiting_for_comment_text)
async def process_comment_text(message: Message, state: FSMContext):
    """Обработать текст комментария"""
    comment_text = message.text
    
    telegram_id = str(message.from_user.id)
    username = message.from_user.username
    first_name = message.from_user.first_name or ''
    last_name = message.from_user.last_name or ''
    
    logger.info(f"📝 Comment text received from {username}: {comment_text[:50]}...")
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user:
        await message.answer("❌ Доступ запрещён")
        await state.clear()
        return
    
    data = await state.get_data()
    task_id = data.get('task_id')
    
    if not task_id:
        await message.answer("❌ Ошибка: задача не найдена")
        await state.clear()
        return
    
    # Добавляем комментарий
    try:
        comment_id = add_comment(task_id, user['id'], comment_text)
        
        # Записываем в историю
        add_task_history_entry(task_id, user['id'], 'comment', None, f"Добавлен комментарий")
        
        # Отправляем уведомления упомянутым пользователям
        from app.main import bot
        await notify_mentioned_users(comment_id, task_id, bot)
        
        await message.answer(
            f"✅ <b>Комментарий добавлен!</b>\n\n"
            f"Задача #{task_id}\n\n"
            f"💬 {comment_text[:100]}...",
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user['role'], is_mobile_device())
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"❌ Error adding comment: {e}", exc_info=True)
        await message.answer("❌ Ошибка при добавлении комментария")
        await state.clear()


@core_router.message(CommentStates.waiting_for_comment_file)
async def process_comment_file(message: Message, state: FSMContext):
    """Обработать файл для комментария"""
    telegram_id = str(message.from_user.id)
    username = message.from_user.username
    first_name = message.from_user.first_name or ''
    last_name = message.from_user.last_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name, last_name)
    if not user:
        await message.answer("❌ Доступ запрещён")
        await state.clear()
        return
    
    data = await state.get_data()
    task_id = data.get('task_id')
    comment_id = data.get('comment_id')
    
    if not task_id or not comment_id:
        await message.answer("❌ Ошибка: данные не найдены")
        await state.clear()
        return
    
    # Обрабатываем файл
    file_id = None
    file_type = None
    file_name = None
    
    if message.photo:
        file_id = message.photo[-1].file_id
        file_type = 'photo'
    elif message.document:
        file_id = message.document.file_id
        file_type = 'document'
        file_name = message.document.file_name
    elif message.video:
        file_id = message.video.file_id
        file_type = 'video'
    elif message.audio:
        file_id = message.audio.file_id
        file_type = 'audio'
    elif message.voice:
        file_id = message.voice.file_id
        file_type = 'voice'
    
    if file_id:
        add_comment_file(comment_id, file_id, file_type, file_name)
        await message.answer("✅ Файл прикреплён к комментарию")
    else:
        await message.answer("❌ Не удалось обработать файл")
    
    await state.clear()

