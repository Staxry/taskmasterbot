"""
FSM States for the Telegram bot
"""
from aiogram.fsm.state import State, StatesGroup


class CreateTaskStates(StatesGroup):
    """Состояния для создания задачи"""
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_priority = State()
    waiting_for_due_date = State()
    waiting_for_manual_due_date = State()
    waiting_for_due_time = State()
    waiting_for_manual_due_time = State()
    waiting_for_assignee = State()
    asking_for_task_photo = State()
    waiting_for_task_photo = State()


class CompleteTaskStates(StatesGroup):
    """Состояния для завершения задачи"""
    waiting_for_comment = State()
    asking_for_photo = State()
    waiting_for_photo = State()


class DeleteTaskStates(StatesGroup):
    """Состояния для удаления задачи"""
    waiting_for_task_id = State()


class AddUserStates(StatesGroup):
    """Состояния для добавления пользователя"""
    waiting_for_username = State()


class RemoveUserStates(StatesGroup):
    """Состояния для удаления пользователя"""
    waiting_for_selection = State()


class SearchTaskStates(StatesGroup):
    """Состояния для поиска задач"""
    waiting_for_query = State()


class ChangeAssigneeStates(StatesGroup):
    """Состояния для смены исполнителя"""
    waiting_for_selection = State()


class ReopenTaskStates(StatesGroup):
    """Состояния для возврата задачи с комментарием"""
    waiting_for_comment = State()


class CommentStates(StatesGroup):
    """Состояния для добавления комментария к задаче"""
    waiting_for_comment_text = State()
    waiting_for_comment_file = State()


class NotificationSettingsStates(StatesGroup):
    """Состояния для настройки уведомлений"""
    waiting_for_quiet_hours_start = State()
    waiting_for_quiet_hours_end = State()
    waiting_for_custom_intervals = State()
