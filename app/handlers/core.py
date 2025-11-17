"""
Core handlers module
Основные команды и меню бота
"""
from datetime import datetime, timedelta
from aiogram import F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from app.handlers import core_router
from app.database import get_db_connection
from app.services.users import get_or_create_user
from app.keyboards.main_menu import get_main_keyboard
from app.keyboards.task_keyboards import get_task_keyboard, get_priority_keyboard, get_due_date_keyboard
from app.keyboards.user_keyboards import get_users_keyboard
from app.states import CreateTaskStates, AddUserStates
from app.logging_config import get_logger

logger = get_logger(__name__)


@core_router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработка команды /start"""
    telegram_id = str(message.from_user.id)
    username = message.from_user.username
    first_name = message.from_user.first_name or ''
    
    logger.info(f"🎯 /start from {telegram_id} (@{username})")
    
    user = get_or_create_user(telegram_id, username, first_name)
    
    if not user:
        logger.warning(f"⛔ Access denied for {telegram_id} (@{username}) - not in whitelist")
        await message.answer(
            "❌ <b>Доступ запрещён</b>\n\n"
            "Ваш username не авторизован в системе.\n"
            "Обратитесь к администратору для получения доступа.\n\n"
            f"Ваш username: @{username or 'отсутствует'}",
            parse_mode='HTML'
        )
        return
    
    role_text = "👨‍💼 Администратор" if user['role'] == 'admin' else "👤 Сотрудник"
    
    logger.info(f"✅ User {username} authorized as {user['role']}")
    
    await message.answer(
        f"👋 Привет, {user['username']}!\n\n"
        f"Роль: <b>{role_text}</b>\n\n"
        f"Выберите действие:",
        parse_mode='HTML',
        reply_markup=get_main_keyboard(user['role'])
    )


@core_router.callback_query(F.data == "help")
async def callback_help(callback: CallbackQuery):
    """Обработка кнопки Помощь"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    
    logger.info(f"❓ Help requested by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    if user['role'] == 'admin':
        text = """📋 <b>Доступные команды (Администратор):</b>

🔹 <b>Мои задачи</b> - список ваших задач
🔹 <b>Все задачи</b> - все задачи в системе
🔹 <b>Создать задачу</b> - добавить новую задачу
🔹 <b>Добавить админа</b> - добавить администратора
🔹 <b>Добавить сотрудника</b> - добавить сотрудника
🔹 Нажмите на задачу для просмотра деталей
🔹 Используйте кнопки для изменения статуса"""
    else:
        text = """📋 <b>Доступные команды (Сотрудник):</b>

🔹 <b>Мои задачи</b> - список ваших задач
🔹 Нажмите на задачу для просмотра деталей
🔹 Используйте кнопки для изменения статуса

<b>Статусы:</b>
⏳ Ожидает | 🔄 В работе | ✅ Завершена | ❌ Отклонена"""
    
    await callback.message.edit_text(
        text,
        parse_mode='HTML',
        reply_markup=get_main_keyboard(user['role'])
    )
    await callback.answer()


@core_router.callback_query(F.data == "add_admin")
async def callback_add_admin(callback: CallbackQuery, state: FSMContext):
    """Начать добавление администратора"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    
    logger.info(f"➕ Add admin requested by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user or user['role'] != 'admin':
        logger.warning(f"⛔ User {username} tried to add admin without permissions")
        await callback.answer("❌ Только администраторы могут добавлять пользователей", show_alert=True)
        return
    
    await state.update_data(target_role='admin')
    await state.set_state(AddUserStates.waiting_for_username)
    
    cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
    ])
    
    logger.debug(f"📝 Starting add admin flow for {username}")
    
    await callback.message.edit_text(
        "👨‍💼 <b>Добавление администратора</b>\n\n"
        "Введите <b>username</b> нового администратора (без @):\n\n"
        "Например: <code>ivan_petrov</code>",
        parse_mode='HTML',
        reply_markup=cancel_keyboard
    )
    await callback.answer()


@core_router.callback_query(F.data == "add_employee")
async def callback_add_employee(callback: CallbackQuery, state: FSMContext):
    """Начать добавление сотрудника"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    
    logger.info(f"➕ Add employee requested by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user or user['role'] != 'admin':
        logger.warning(f"⛔ User {username} tried to add employee without permissions")
        await callback.answer("❌ Только администраторы могут добавлять пользователей", show_alert=True)
        return
    
    await state.update_data(target_role='employee')
    await state.set_state(AddUserStates.waiting_for_username)
    
    cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
    ])
    
    logger.debug(f"📝 Starting add employee flow for {username}")
    
    await callback.message.edit_text(
        "👤 <b>Добавление сотрудника</b>\n\n"
        "Введите <b>username</b> нового сотрудника (без @):\n\n"
        "Например: <code>maria_ivanova</code>",
        parse_mode='HTML',
        reply_markup=cancel_keyboard
    )
    await callback.answer()


@core_router.message(AddUserStates.waiting_for_username)
async def process_add_user(message: Message, state: FSMContext):
    """Обработка username для добавления пользователя"""
    new_username = message.text.strip().replace('@', '')
    
    logger.info(f"📥 Processing add user: {new_username}")
    
    if not new_username:
        logger.warning(f"⚠️ Empty username provided")
        await message.answer("❌ Username не может быть пустым. Попробуйте ещё раз:")
        return
    
    data = await state.get_data()
    target_role = data.get('target_role', 'employee')
    
    telegram_id = str(message.from_user.id)
    username = message.from_user.username
    first_name = message.from_user.first_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user:
        logger.error(f"❌ User {username} lost authorization during add user flow")
        await message.answer("❌ Доступ запрещён")
        await state.clear()
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        logger.debug(f"💾 Adding {new_username} as {target_role} to whitelist")
        
        cur.execute(
            """INSERT INTO allowed_users (username, role, added_by_id, created_at)
               VALUES (%s, %s, %s, NOW())
               ON CONFLICT (username) 
               DO UPDATE SET role = EXCLUDED.role, added_by_id = EXCLUDED.added_by_id""",
            (new_username, target_role, user['id'])
        )
        conn.commit()
        
        role_text = "👨‍💼 Администратор" if target_role == 'admin' else "👤 Сотрудник"
        
        logger.info(f"✅ {username} added {new_username} as {target_role}")
        
        await message.answer(
            f"✅ <b>Пользователь добавлен!</b>\n\n"
            f"Username: @{new_username}\n"
            f"Роль: {role_text}\n\n"
            f"Теперь пользователь @{new_username} может отправить /start боту для авторизации.",
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user['role'])
        )
        
        await state.clear()
    
    except Exception as e:
        logger.error(f"❌ Error adding user {new_username}: {e}", exc_info=True)
        await message.answer(
            f"❌ Ошибка при добавлении пользователя: {str(e)}",
            reply_markup=get_main_keyboard(user['role'])
        )
        await state.clear()
    finally:
        cur.close()
        conn.close()


@core_router.callback_query(F.data == "my_tasks")
async def callback_my_tasks(callback: CallbackQuery):
    """Обработка кнопки Мои задачи"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    
    logger.info(f"📋 My tasks requested by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        if user['role'] == 'admin':
            logger.debug(f"📊 Fetching all tasks for admin {username}")
            cur.execute(
                """SELECT id, title, status, priority, due_date, assigned_to_id
                   FROM tasks 
                   ORDER BY created_at DESC
                   LIMIT 20"""
            )
        else:
            logger.debug(f"📊 Fetching tasks for employee {username} (id={user['id']})")
            cur.execute(
                """SELECT id, title, status, priority, due_date, assigned_to_id
                   FROM tasks 
                   WHERE assigned_to_id = %s OR assigned_to_id IS NULL
                   ORDER BY created_at DESC
                   LIMIT 20""",
                (user['id'],)
            )
        tasks = cur.fetchall()
        
        logger.info(f"📊 Found {len(tasks)} tasks for {username}")
        
        if not tasks:
            try:
                await callback.message.edit_text(
                    "📋 У вас пока нет задач.",
                    reply_markup=get_main_keyboard(user['role'])
                )
            except Exception:
                await callback.message.delete()
                await callback.message.answer(
                    "📋 У вас пока нет задач.",
                    reply_markup=get_main_keyboard(user['role'])
                )
            await callback.answer()
            return
        
        buttons = []
        
        status_emoji = {
            'pending': '⏳',
            'in_progress': '🔄',
            'partially_completed': '🔶',
            'completed': '✅',
            'rejected': '❌'
        }
        
        priority_emoji = {
            'urgent': '🔴',
            'high': '🟠',
            'medium': '🟡',
            'low': '🟢'
        }
        
        for task in tasks[:10]:
            task_id, title, status, priority, due_date, assigned_to_id = task
            emoji_status = status_emoji.get(status, '📌')
            emoji_priority = priority_emoji.get(priority, '📌')
            
            if assigned_to_id is None:
                button_text = f"🆓 {emoji_priority} {title[:20]}"
            else:
                button_text = f"{emoji_status} {emoji_priority} {title[:25]}"
            
            buttons.append([
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"task_{task_id}"
                )
            ])
        
        buttons.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        try:
            await callback.message.edit_text(
                "📋 <b>Выберите задачу:</b>",
                parse_mode='HTML',
                reply_markup=keyboard
            )
        except Exception:
            await callback.message.delete()
            await callback.message.answer(
                "📋 <b>Выберите задачу:</b>",
                parse_mode='HTML',
                reply_markup=keyboard
            )
        await callback.answer()
    
    finally:
        cur.close()
        conn.close()


@core_router.callback_query(F.data == "all_tasks")
async def callback_all_tasks(callback: CallbackQuery):
    """Обработка кнопки Все задачи"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    
    logger.info(f"📊 All tasks requested by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    if user['role'] != 'admin':
        logger.warning(f"⛔ User {username} tried to view all tasks without admin rights")
        await callback.answer("❌ Только администраторы могут просматривать все задачи.", show_alert=True)
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        logger.debug(f"📊 Fetching all tasks for admin {username}")
        
        cur.execute(
            """SELECT t.id, t.title, t.status, t.priority, u.username
               FROM tasks t
               LEFT JOIN users u ON t.assigned_to_id = u.id
               ORDER BY t.created_at DESC
               LIMIT 20"""
        )
        tasks = cur.fetchall()
        
        logger.info(f"📊 Found {len(tasks)} total tasks in system")
        
        if not tasks:
            await callback.message.edit_text(
                "📋 В системе пока нет задач.",
                reply_markup=get_main_keyboard(user['role'])
            )
            await callback.answer()
            return
        
        buttons = []
        
        status_emoji = {
            'pending': '⏳',
            'in_progress': '🔄',
            'partially_completed': '🔶',
            'completed': '✅',
            'rejected': '❌'
        }
        
        priority_emoji = {
            'urgent': '🔴',
            'high': '🟠',
            'medium': '🟡',
            'low': '🟢'
        }
        
        for task in tasks[:10]:
            task_id, title, status, priority, assigned_username = task
            emoji_status = status_emoji.get(status, '📌')
            emoji_priority = priority_emoji.get(priority, '📌')
            
            button_text = f"{emoji_status} {emoji_priority} {title[:20]}"
            buttons.append([
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"task_{task_id}"
                )
            ])
        
        buttons.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await callback.message.edit_text(
            f"📋 <b>Все задачи в системе ({len(tasks)}):</b>",
            parse_mode='HTML',
            reply_markup=keyboard
        )
        await callback.answer()
    
    finally:
        cur.close()
        conn.close()


@core_router.callback_query(F.data.startswith("task_") & ~F.data.in_({"task_photo_yes", "task_photo_no"}))
async def callback_task_details(callback: CallbackQuery):
    """Показать детали задачи"""
    task_id = int(callback.data.split('_')[1])
    
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    
    logger.info(f"📂 Task #{task_id} details requested by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            """SELECT t.id, t.title, t.description, t.status, t.priority, t.due_date, 
                      u.username, t.created_at, t.assigned_to_id, t.completion_comment, t.photo_file_id
               FROM tasks t
               LEFT JOIN users u ON t.assigned_to_id = u.id
               WHERE t.id = %s""",
            (task_id,)
        )
        task = cur.fetchone()
        
        if not task:
            logger.warning(f"⚠️ Task #{task_id} not found")
            await callback.answer("❌ Задача не найдена.", show_alert=True)
            return
        
        tid, title, description, status, priority, due_date, assigned_username, created_at, assigned_to_id, completion_comment, photo_file_id = task
        
        logger.debug(f"📊 Task #{tid}: status={status}, assigned_to={assigned_username}, has_photo={bool(photo_file_id)}")
        
        status_text = {
            'pending': '⏳ Ожидает',
            'in_progress': '🔄 В работе',
            'partially_completed': '🔶 Частично завершена',
            'completed': '✅ Завершена',
            'rejected': '❌ Отклонена'
        }.get(status, status)
        
        priority_text = {
            'urgent': '🔴 Срочно',
            'high': '🟠 Высокий',
            'medium': '🟡 Средний',
            'low': '🟢 Низкий'
        }.get(priority, priority)
        
        text = f"""📋 <b>Задача #{tid}</b>

<b>Название:</b> {title}
<b>Описание:</b> {description or 'Нет описания'}
<b>Статус:</b> {status_text}
<b>Приоритет:</b> {priority_text}
<b>Срок:</b> {due_date}
<b>Назначена:</b> @{assigned_username or '🆓 Свободна (можно взять)'}
<b>Создана:</b> {created_at.strftime('%Y-%m-%d %H:%M')}
"""
        
        if status in ['completed', 'partially_completed'] and completion_comment:
            text += f"\n\n💬 <b>Комментарий:</b>\n{completion_comment}"
        
        if assigned_to_id is None:
            text += "\n\n💡 Эта задача свободна - любой сотрудник может взять её в работу!"
        elif status not in ['completed', 'partially_completed']:
            text += "\n\nВыберите новый статус:"
        
        if status in ['completed', 'partially_completed'] and photo_file_id:
            logger.debug(f"📸 Sending task #{tid} with completion photo")
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=photo_file_id,
                caption=text,
                parse_mode='HTML',
                reply_markup=get_task_keyboard(task_id, status, assigned_to_id, user['id'], user['role'] == 'admin')
            )
        else:
            try:
                await callback.message.edit_text(
                    text,
                    parse_mode='HTML',
                    reply_markup=get_task_keyboard(task_id, status, assigned_to_id, user['id'], user['role'] == 'admin')
                )
            except Exception:
                logger.debug(f"⚠️ Could not edit message, deleting and resending")
                await callback.message.delete()
                await callback.message.answer(
                    text,
                    parse_mode='HTML',
                    reply_markup=get_task_keyboard(task_id, status, assigned_to_id, user['id'], user['role'] == 'admin')
                )
        
        await callback.answer()
    
    finally:
        cur.close()
        conn.close()


@core_router.callback_query(F.data.startswith("take_"))
async def callback_take_task(callback: CallbackQuery):
    """Взять задачу в работу"""
    task_id = int(callback.data.split('_')[1])
    
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    
    logger.info(f"✋ Take task #{task_id} requested by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    if user['role'] == 'admin':
        logger.warning(f"⛔ Admin {username} tried to take task #{task_id}")
        await callback.answer("❌ Админы не могут брать задачи в работу. Используйте назначение через создание задачи.", show_alert=True)
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            """SELECT id, title, description, priority, due_date, assigned_to_id, created_by_id, task_photo_file_id 
               FROM tasks WHERE id = %s""",
            (task_id,)
        )
        task = cur.fetchone()
        
        if not task:
            logger.warning(f"⚠️ Task #{task_id} not found")
            await callback.answer("❌ Задача не найдена.", show_alert=True)
            return
        
        task_id_db, title, description, priority, due_date, assigned_to_id, created_by_id, task_photo_file_id = task
        
        logger.info(f"📋 Task #{task_id_db} info: assigned_to={assigned_to_id}, has_photo={bool(task_photo_file_id)}")
        
        if assigned_to_id is not None:
            logger.warning(f"⚠️ Task #{task_id} already assigned to user {assigned_to_id}")
            await callback.answer("❌ Эта задача уже назначена другому сотруднику.", show_alert=True)
            return
        
        cur.execute(
            "UPDATE tasks SET assigned_to_id = %s, status = 'in_progress', updated_at = NOW() WHERE id = %s",
            (user['id'], task_id)
        )
        conn.commit()
        
        logger.info(f"✅ Task #{task_id} assigned to {username} (id={user['id']})")
        
        await callback.answer("✅ Задача взята в работу!", show_alert=True)
        
        if created_by_id:
            cur.execute(
                "SELECT telegram_id, username FROM users WHERE id = %s",
                (created_by_id,)
            )
            creator = cur.fetchone()
            
            if creator:
                creator_telegram_id, creator_username = creator
                
                priority_text = {
                    'urgent': '🔴 Срочно',
                    'high': '🟠 Высокий',
                    'medium': '🟡 Средний',
                    'low': '🟢 Низкий'
                }.get(priority, priority)
                
                notification_text = f"""✋ <b>Задачу взяли в работу!</b>

<b>Задача #{task_id}</b>
<b>Название:</b> {title}
<b>Описание:</b> {description or 'Нет описания'}
<b>Приоритет:</b> {priority_text}
<b>Срок:</b> 📅 {due_date}
<b>Исполнитель:</b> @{username}
<b>Статус:</b> 🔄 В работе

Нажмите кнопку ниже для просмотра задачи."""
                
                task_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📂 Открыть задачу", callback_data=f"task_{task_id}")]
                ])
                
                try:
                    if task_photo_file_id:
                        logger.info(f"📸 Sending notification WITH photo to admin {creator_username}")
                        await callback.message.bot.send_photo(
                            chat_id=creator_telegram_id,
                            photo=task_photo_file_id,
                            caption=notification_text,
                            parse_mode='HTML',
                            reply_markup=task_keyboard
                        )
                    else:
                        logger.info(f"📝 Sending notification WITHOUT photo to admin {creator_username}")
                        await callback.message.bot.send_message(
                            chat_id=creator_telegram_id,
                            text=notification_text,
                            parse_mode='HTML',
                            reply_markup=task_keyboard
                        )
                    logger.info(f"✅ Task assignment notification sent to {creator_username}")
                except Exception as notif_error:
                    logger.warning(f"⚠️ Could not send notification: {notif_error}")
        
        await callback.message.edit_text(
            f"✅ <b>Задача взята в работу!</b>\n\n"
            f"Задача: {title}\n"
            f"Теперь она назначена на вас.\n\n"
            f"Используйте 📋 Мои задачи для просмотра.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 Мои задачи", callback_data="my_tasks")],
                [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
            ])
        )
        
        logger.info(f"✅ {username} took task #{task_id} in progress")
    
    except Exception as e:
        logger.error(f"❌ Error taking task #{task_id}: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)
    finally:
        cur.close()
        conn.close()


@core_router.callback_query(F.data == "create_task")
async def callback_create_task(callback: CallbackQuery, state: FSMContext):
    """Начать создание задачи"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    
    logger.info(f"➕ Create task requested by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    if user['role'] != 'admin':
        logger.warning(f"⛔ User {username} tried to create task without admin rights")
        await callback.answer("❌ Только администраторы могут создавать задачи.", show_alert=True)
        return
    
    await state.set_state(CreateTaskStates.waiting_for_title)
    
    cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
    ])
    
    logger.debug(f"📝 Starting create task flow for {username}")
    
    await callback.message.edit_text(
        "➕ <b>Создание задачи</b>\n\n"
        "Введите <b>название задачи</b>:",
        parse_mode='HTML',
        reply_markup=cancel_keyboard
    )
    await callback.answer()


@core_router.message(CreateTaskStates.waiting_for_title)
async def process_task_title(message: Message, state: FSMContext):
    """Получить название задачи"""
    logger.info(f"📝 Task title received: {message.text[:30]}...")
    
    await state.update_data(title=message.text)
    await state.set_state(CreateTaskStates.waiting_for_description)
    
    skip_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_description")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
    ])
    
    await message.answer(
        "Введите <b>описание задачи</b> (или нажмите Пропустить):",
        parse_mode='HTML',
        reply_markup=skip_keyboard
    )


@core_router.callback_query(F.data == "skip_description", CreateTaskStates.waiting_for_description)
async def skip_description(callback: CallbackQuery, state: FSMContext):
    """Пропустить описание"""
    logger.debug("⏭ Task description skipped")
    
    await state.update_data(description="")
    await state.set_state(CreateTaskStates.waiting_for_priority)
    
    await callback.message.edit_text(
        "Выберите <b>приоритет задачи</b>:",
        parse_mode='HTML',
        reply_markup=get_priority_keyboard()
    )
    await callback.answer()


@core_router.message(CreateTaskStates.waiting_for_description)
async def process_task_description(message: Message, state: FSMContext):
    """Получить описание задачи"""
    logger.info(f"📝 Task description received: {message.text[:30]}...")
    
    await state.update_data(description=message.text)
    await state.set_state(CreateTaskStates.waiting_for_priority)
    
    await message.answer(
        "Выберите <b>приоритет задачи</b>:",
        parse_mode='HTML',
        reply_markup=get_priority_keyboard()
    )


@core_router.callback_query(F.data.startswith("priority_"))
async def process_priority(callback: CallbackQuery, state: FSMContext):
    """Обработать выбор приоритета и перейти к выбору срока"""
    priority = callback.data.split('_')[1]
    
    logger.info(f"📊 Task priority selected: {priority}")
    
    await state.update_data(priority=priority)
    await state.set_state(CreateTaskStates.waiting_for_due_date)
    
    await callback.message.edit_text(
        "📅 <b>Выберите срок выполнения задачи:</b>",
        parse_mode='HTML',
        reply_markup=get_due_date_keyboard()
    )
    await callback.answer()


@core_router.callback_query(F.data.startswith("due_"))
async def process_due_date(callback: CallbackQuery, state: FSMContext):
    """Обработать выбор срока и перейти к выбору исполнителя"""
    due_date = callback.data.split('_', 1)[1]
    
    if due_date == "manual":
        logger.debug("✍️ Manual due date input requested")
        await state.set_state(CreateTaskStates.waiting_for_manual_due_date)
        await callback.message.edit_text(
            "✍️ <b>Введите дату вручную</b>\n\n"
            "Формат: <code>ГГГГ-ММ-ДД</code> (например: 2024-12-31)\n"
            "Или: <code>ДД.ММ.ГГГГ</code> (например: 31.12.2024)",
            parse_mode='HTML'
        )
        await callback.answer()
        return
    
    logger.info(f"📅 Task due date selected: {due_date}")
    
    await state.update_data(due_date=due_date)
    await state.set_state(CreateTaskStates.waiting_for_assignee)
    
    await callback.message.edit_text(
        "👥 <b>Выберите исполнителя задачи:</b>",
        parse_mode='HTML',
        reply_markup=get_users_keyboard()
    )
    await callback.answer()


@core_router.message(CreateTaskStates.waiting_for_manual_due_date)
async def process_manual_due_date(message: Message, state: FSMContext):
    """Обработать ручной ввод даты"""
    date_text = message.text.strip()
    
    logger.info(f"📅 Manual due date input: {date_text}")
    
    due_date = None
    try:
        if '-' in date_text:
            parsed_date = datetime.strptime(date_text, '%Y-%m-%d')
            due_date = parsed_date.strftime('%Y-%m-%d')
        elif '.' in date_text:
            parsed_date = datetime.strptime(date_text, '%d.%m.%Y')
            due_date = parsed_date.strftime('%Y-%m-%d')
        else:
            raise ValueError("Неизвестный формат")
    except ValueError as e:
        logger.warning(f"⚠️ Invalid date format: {date_text} - {e}")
        await message.answer(
            "❌ <b>Неверный формат даты!</b>\n\n"
            "Используйте один из форматов:\n"
            "• <code>ГГГГ-ММ-ДД</code> (например: 2024-12-31)\n"
            "• <code>ДД.ММ.ГГГГ</code> (например: 31.12.2024)\n\n"
            "Попробуйте ещё раз:",
            parse_mode='HTML'
        )
        return
    
    logger.info(f"✅ Manual due date parsed: {due_date}")
    
    await state.update_data(due_date=due_date)
    await state.set_state(CreateTaskStates.waiting_for_assignee)
    
    await message.answer(
        "👥 <b>Выберите исполнителя задачи:</b>",
        parse_mode='HTML',
        reply_markup=get_users_keyboard()
    )


@core_router.callback_query(F.data.startswith("assignee_"))
async def process_assignee(callback: CallbackQuery, state: FSMContext):
    """Выбрать исполнителя и спросить про фото"""
    assignee_str = callback.data.split('_')[1]
    
    if assignee_str == "none":
        assignee_id = None
        logger.info("👤 No assignee selected (free task)")
    else:
        assignee_id = int(assignee_str)
        logger.info(f"👤 Assignee selected: user_id={assignee_id}")
    
    await state.update_data(assignee_id=assignee_id)
    await state.set_state(CreateTaskStates.asking_for_task_photo)
    
    photo_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, добавить фото", callback_data="task_photo_yes"),
            InlineKeyboardButton(text="❌ Нет, без фото", callback_data="task_photo_no")
        ]
    ])
    
    await callback.message.edit_text(
        "📸 <b>Добавить фото к задаче?</b>\n\n"
        "Фото поможет лучше объяснить задачу исполнителю.",
        parse_mode='HTML',
        reply_markup=photo_keyboard
    )
    await callback.answer()


@core_router.callback_query(F.data == "delete_task_menu")
async def callback_delete_task_menu(callback: CallbackQuery):
    """Показать список незавершённых задач для удаления"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    
    logger.info(f"🗑️ Delete task menu requested by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    if user['role'] != 'admin':
        logger.warning(f"⛔ User {username} tried to delete tasks without admin rights")
        await callback.answer("❌ Только администраторы могут удалять задачи.", show_alert=True)
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        logger.debug("📊 Fetching uncompleted tasks for deletion")
        
        cur.execute(
            """SELECT t.id, t.title, t.status, t.priority, u.username
               FROM tasks t
               LEFT JOIN users u ON t.assigned_to_id = u.id
               WHERE t.status != 'completed'
               ORDER BY t.created_at DESC
               LIMIT 20"""
        )
        tasks = cur.fetchall()
        
        logger.info(f"📊 Found {len(tasks)} uncompleted tasks")
        
        if not tasks:
            await callback.message.edit_text(
                "📋 Нет незавершённых задач для удаления.",
                reply_markup=get_main_keyboard(user['role'])
            )
            await callback.answer()
            return
        
        buttons = []
        
        status_emoji = {
            'pending': '⏳',
            'in_progress': '🔄',
            'rejected': '❌'
        }
        
        priority_emoji = {
            'urgent': '🔴',
            'high': '🟠',
            'medium': '🟡',
            'low': '🟢'
        }
        
        for task in tasks:
            task_id, title, status, priority, assigned_username = task
            emoji_status = status_emoji.get(status, '📌')
            emoji_priority = priority_emoji.get(priority, '📌')
            
            button_text = f"{emoji_status} {emoji_priority} {title[:25]}"
            buttons.append([
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"delete_confirm_{task_id}"
                )
            ])
        
        buttons.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await callback.message.edit_text(
            f"🗑️ <b>Выберите задачу для удаления:</b>\n\n"
            f"Показаны незавершённые задачи ({len(tasks)})\n"
            f"⚠️ Внимание: удаление необратимо!",
            parse_mode='HTML',
            reply_markup=keyboard
        )
        await callback.answer()
    
    finally:
        cur.close()
        conn.close()


@core_router.callback_query(F.data.startswith("delete_confirm_"))
async def callback_delete_confirm(callback: CallbackQuery):
    """Удалить задачу после подтверждения"""
    task_id = int(callback.data.split('_')[2])
    
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    
    logger.info(f"🗑️ Delete task #{task_id} confirmation by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    if user['role'] != 'admin':
        logger.warning(f"⛔ User {username} tried to delete task without admin rights")
        await callback.answer("❌ Только администраторы могут удалять задачи.", show_alert=True)
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            "SELECT title FROM tasks WHERE id = %s",
            (task_id,)
        )
        task = cur.fetchone()
        
        if not task:
            logger.warning(f"⚠️ Task #{task_id} not found for deletion")
            await callback.answer("❌ Задача не найдена.", show_alert=True)
            return
        
        task_title = task[0]
        
        cur.execute(
            "DELETE FROM tasks WHERE id = %s",
            (task_id,)
        )
        conn.commit()
        
        logger.info(f"✅ Task #{task_id} ({task_title}) deleted by {username}")
        
        await callback.message.edit_text(
            f"✅ <b>Задача удалена!</b>\n\n"
            f"ID: {task_id}\n"
            f"Название: {task_title}\n\n"
            f"Задача полностью удалена из системы.",
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user['role'])
        )
        await callback.answer("✅ Задача удалена", show_alert=True)
    
    except Exception as e:
        logger.error(f"❌ Error deleting task #{task_id}: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при удалении задачи", show_alert=True)
    finally:
        cur.close()
        conn.close()


@core_router.callback_query(F.data == "remove_admin")
async def callback_remove_admin(callback: CallbackQuery):
    """Показать список админов для удаления"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    
    logger.info(f"🗑️ Remove admin requested by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    if user['role'] != 'admin':
        logger.warning(f"⛔ User {username} tried to remove admin without permissions")
        await callback.answer("❌ Только администраторы могут удалять пользователей.", show_alert=True)
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            "SELECT id, username FROM users WHERE role = 'admin' AND telegram_id != %s ORDER BY username",
            (telegram_id,)
        )
        admins = cur.fetchall()
        
        logger.info(f"📊 Found {len(admins)} other admins")
        
        if not admins:
            await callback.message.edit_text(
                "👨‍💼 <b>Нет других администраторов для удаления</b>",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
                ])
            )
            await callback.answer()
            return
        
        buttons = []
        for admin_id, admin_username in admins:
            buttons.append([
                InlineKeyboardButton(
                    text=f"🗑️ @{admin_username}",
                    callback_data=f"confirmremove_{admin_id}_admin"
                )
            ])
        
        buttons.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")])
        
        await callback.message.edit_text(
            "👨‍💼 <b>Выберите администратора для удаления:</b>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
        await callback.answer()
    
    finally:
        cur.close()
        conn.close()


@core_router.callback_query(F.data == "remove_employee")
async def callback_remove_employee(callback: CallbackQuery):
    """Показать список сотрудников для удаления"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    
    logger.info(f"🗑️ Remove employee requested by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    if user['role'] != 'admin':
        logger.warning(f"⛔ User {username} tried to remove employee without permissions")
        await callback.answer("❌ Только администраторы могут удалять пользователей.", show_alert=True)
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            "SELECT id, username FROM users WHERE role = 'employee' ORDER BY username"
        )
        employees = cur.fetchall()
        
        logger.info(f"📊 Found {len(employees)} employees")
        
        if not employees:
            await callback.message.edit_text(
                "👤 <b>Нет сотрудников для удаления</b>",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
                ])
            )
            await callback.answer()
            return
        
        buttons = []
        for emp_id, emp_username in employees:
            buttons.append([
                InlineKeyboardButton(
                    text=f"🗑️ @{emp_username}",
                    callback_data=f"confirmremove_{emp_id}_employee"
                )
            ])
        
        buttons.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")])
        
        await callback.message.edit_text(
            "👤 <b>Выберите сотрудника для удаления:</b>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
        await callback.answer()
    
    finally:
        cur.close()
        conn.close()


@core_router.callback_query(F.data.startswith("confirmremove_"))
async def callback_confirm_remove_user(callback: CallbackQuery):
    """Подтверждение удаления пользователя"""
    parts = callback.data.split('_')
    user_id_to_remove = int(parts[1])
    user_type = parts[2]
    
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    
    logger.info(f"🗑️ Confirm remove user {user_id_to_remove} ({user_type}) by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    if user['role'] != 'admin':
        logger.warning(f"⛔ User {username} tried to remove user without permissions")
        await callback.answer("❌ Только администраторы могут удалять пользователей.", show_alert=True)
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            "SELECT username, role FROM users WHERE id = %s",
            (user_id_to_remove,)
        )
        user_to_remove = cur.fetchone()
        
        if not user_to_remove:
            logger.warning(f"⚠️ User {user_id_to_remove} not found for removal")
            await callback.answer("❌ Пользователь не найден.", show_alert=True)
            return
        
        username_to_remove, role_to_remove = user_to_remove
        
        logger.debug(f"🗑️ Removing user: {username_to_remove} ({role_to_remove})")
        
        cur.execute("DELETE FROM users WHERE id = %s", (user_id_to_remove,))
        cur.execute("DELETE FROM allowed_users WHERE username = %s", (username_to_remove,))
        cur.execute("UPDATE tasks SET assigned_to_id = NULL WHERE assigned_to_id = %s", (user_id_to_remove,))
        
        conn.commit()
        
        role_text = "👨‍💼 Администратор" if role_to_remove == 'admin' else "👤 Сотрудник"
        
        logger.info(f"✅ Admin {username} removed user {username_to_remove} ({role_to_remove})")
        
        await callback.message.edit_text(
            f"✅ <b>Пользователь удалён!</b>\n\n"
            f"Username: @{username_to_remove}\n"
            f"Роль: {role_text}\n\n"
            f"Задачи, которые были назначены на этого пользователя, теперь свободны.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
            ])
        )
        await callback.answer()
    
    except Exception as e:
        logger.error(f"❌ Error removing user {user_id_to_remove}: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка при удалении: {str(e)}", show_alert=True)
    finally:
        cur.close()
        conn.close()


@core_router.callback_query(F.data == "cancel")
async def callback_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена текущей операции"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    
    logger.info(f"❌ Cancel operation by {username}")
    
    await state.clear()
    
    first_name = callback.from_user.first_name or ''
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user:
        await callback.message.edit_text("❌ Доступ запрещён")
        await callback.answer()
        return
    
    await callback.message.edit_text(
        "❌ Операция отменена.\n\nВыберите действие:",
        reply_markup=get_main_keyboard(user['role'])
    )
    await callback.answer()


@core_router.callback_query(F.data == "back_to_main")
async def callback_back_to_main(callback: CallbackQuery):
    """Вернуться в главное меню"""
    telegram_id = str(callback.from_user.id)
    username = callback.from_user.username
    first_name = callback.from_user.first_name or ''
    
    logger.info(f"🔙 Back to main menu by {username}")
    
    user = get_or_create_user(telegram_id, username, first_name)
    if not user:
        await callback.message.edit_text("❌ Доступ запрещён")
        await callback.answer()
        return
    
    role_text = "👨‍💼 Администратор" if user['role'] == 'admin' else "👤 Сотрудник"
    
    await callback.message.edit_text(
        f"👋 Привет, {user['username']}!\n\n"
        f"Роль: <b>{role_text}</b>\n\n"
        f"Выберите действие:",
        parse_mode='HTML',
        reply_markup=get_main_keyboard(user['role'])
    )
    await callback.answer()


@core_router.message()
async def handle_unauthorized(message: Message):
    """Обработка сообщений от неавторизованных пользователей"""
    telegram_id = str(message.from_user.id)
    username = message.from_user.username
    first_name = message.from_user.first_name or ''
    
    logger.info(f"📨 Message from {telegram_id} (@{username}): {message.text[:30] if message.text else 'non-text'}")
    
    user = get_or_create_user(telegram_id, username, first_name)
    
    if not user:
        logger.warning(f"⛔ Unauthorized access attempt by {telegram_id} (@{username})")
        await message.answer(
            "❌ <b>Доступ запрещён</b>\n\n"
            "Ваш username не авторизован в системе.\n"
            "Обратитесь к администратору для получения доступа.\n\n"
            f"Ваш username: @{username or 'отсутствует'}",
            parse_mode='HTML'
        )
