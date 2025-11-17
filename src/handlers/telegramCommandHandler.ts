import { db } from '../../shared/db';
import { users, tasks } from '../../shared/schema';
import { eq, and, gte } from 'drizzle-orm';

export interface TelegramMessage {
  telegramId: string;
  username?: string;
  firstName?: string;
  messageText: string;
}

export interface CommandResult {
  response: string;
  success: boolean;
}

export async function handleTelegramCommand(
  message: TelegramMessage
): Promise<CommandResult> {
  const { telegramId, username, firstName, messageText } = message;

  const trimmedText = messageText.trim();
  const command = trimmedText.split(' ')[0].toLowerCase();
  const args = trimmedText.substring(command.length).trim();

  let user = await db
    .select()
    .from(users)
    .where(eq(users.telegramId, telegramId))
    .limit(1)
    .then((rows) => rows[0]);

  if (!user && command !== '/start') {
    return {
      response: 'Пожалуйста, начните с команды /start для регистрации.',
      success: false,
    };
  }

  switch (command) {
    case '/start':
      return await handleStart(telegramId, username, firstName);

    case '/help':
    case '/помощь':
      return handleHelp(user!.role);

    case '/create_task':
    case '/создать_задачу':
      return await handleCreateTask(user!, args);

    case '/my_tasks':
    case '/мои_задачи':
      return await handleMyTasks(user!);

    case '/all_tasks':
    case '/все_задачи':
      return await handleAllTasks(user!);

    case '/update_status':
    case '/обновить_статус':
      return await handleUpdateStatus(user!, args);

    case '/task_details':
    case '/детали_задачи':
      return await handleTaskDetails(user!, args);

    default:
      return {
        response: `Неизвестная команда: ${command}\n\nИспользуйте /help для списка доступных команд.`,
        success: false,
      };
  }
}

async function handleStart(
  telegramId: string,
  username?: string,
  firstName?: string
): Promise<CommandResult> {
  let user = await db
    .select()
    .from(users)
    .where(eq(users.telegramId, telegramId))
    .limit(1)
    .then((rows) => rows[0]);

  if (user) {
    return {
      response: `С возвращением, ${firstName || username || 'пользователь'}!\n\nВаша роль: ${user.role === 'admin' ? 'Администратор' : 'Сотрудник'}\n\nИспользуйте /help для списка команд.`,
      success: true,
    };
  }

  const [newUser] = await db
    .insert(users)
    .values({
      telegramId,
      username: username || null,
      role: 'employee',
    })
    .returning();

  return {
    response: `Добро пожаловать, ${firstName || username || 'пользователь'}! 🎉\n\nВы зарегистрированы как *Сотрудник*.\n\nДоступные команды:\n/help - список всех команд\n/my_tasks - мои задачи\n/update_status - обновить статус задачи`,
    success: true,
  };
}

function handleHelp(role: string): CommandResult {
  const commonCommands = `
📋 *Доступные команды:*

/help - показать это сообщение
/my_tasks - показать мои задачи
/task_details <ID> - детали задачи
/update_status <ID> <статус> - обновить статус задачи
  Статусы: pending, in_progress, completed, rejected
`;

  const adminCommands = `
/create_task - создать новую задачу
/all_tasks - показать все задачи
`;

  if (role === 'admin') {
    return {
      response: commonCommands + '\n*Команды администратора:*\n' + adminCommands,
      success: true,
    };
  }

  return {
    response: commonCommands,
    success: true,
  };
}

async function handleCreateTask(
  user: any,
  args: string
): Promise<CommandResult> {
  if (user.role !== 'admin') {
    return {
      response: 'Только администраторы могут создавать задачи.',
      success: false,
    };
  }

  if (!args) {
    return {
      response: `Использование: /create_task <параметры>

Пример:
/create_task title:"Подготовить отчет" description:"Квартальный отчет" priority:high due_date:2025-12-25

Параметры:
- title:"..." (обязательно)
- description:"..." (опционально)
- priority: low/medium/high/urgent (по умолчанию: medium)
- due_date: YYYY-MM-DD (опционально)
- assigned_to: telegram_id сотрудника (опционально, по умолчанию: вам)`,
      success: false,
    };
  }

  try {
    const params = parseTaskParams(args);

    if (!params.title) {
      return {
        response: 'Необходимо указать название задачи (title:"...")',
        success: false,
      };
    }

    let assignedToUserId = user.id;
    let assignedToInfo = 'вам';

    if (params.assignedToTelegramId) {
      if (!params.assignedToTelegramId.match(/^\d+$/)) {
        return {
          response: `Некорректный Telegram ID: ${params.assignedToTelegramId}. Telegram ID должен содержать только цифры.`,
          success: false,
        };
      }

      console.log(`[handleCreateTask] Looking up user with Telegram ID: ${params.assignedToTelegramId}`);

      const assignedUser = await db
        .select()
        .from(users)
        .where(eq(users.telegramId, params.assignedToTelegramId))
        .limit(1)
        .then((rows) => rows[0]);

      if (!assignedUser) {
        console.log(`[handleCreateTask] User not found with Telegram ID: ${params.assignedToTelegramId}`);
        return {
          response: `Пользователь с Telegram ID ${params.assignedToTelegramId} не найден в системе. Пользователь должен сначала отправить /start боту.`,
          success: false,
        };
      }

      console.log(`[handleCreateTask] Found user #${assignedUser.id} for Telegram ID: ${params.assignedToTelegramId}`);
      assignedToUserId = assignedUser.id;
      assignedToInfo = `User #${assignedUser.id} (Telegram ID: ${params.assignedToTelegramId})`;
    }

    const [newTask] = await db
      .insert(tasks)
      .values({
        title: params.title,
        description: params.description || '',
        priority: params.priority || 'medium',
        status: 'pending',
        dueDate: params.dueDate || new Date(),
        assignedToId: assignedToUserId,
        createdById: user.id,
      })
      .returning();

    console.log(`[handleCreateTask] Task #${newTask.id} created and assigned to user #${assignedToUserId}`);

    return {
      response: `✅ Задача создана успешно!\n\nID: ${newTask.id}\nНазвание: ${newTask.title}\nПриоритет: ${newTask.priority}\nСтатус: pending\nНазначена: ${assignedToInfo}`,
      success: true,
    };
  } catch (error) {
    return {
      response: `Ошибка при создании задачи: ${error instanceof Error ? error.message : 'Неизвестная ошибка'}`,
      success: false,
    };
  }
}

async function handleMyTasks(user: any): Promise<CommandResult> {
  const userTasks = await db
    .select()
    .from(tasks)
    .where(eq(tasks.assignedToId, user.id));

  if (userTasks.length === 0) {
    return {
      response: 'У вас пока нет назначенных задач.',
      success: true,
    };
  }

  const taskList = userTasks
    .map(
      (task) =>
        `📌 *ID ${task.id}*: ${task.title}\n` +
        `   Статус: ${task.status}\n` +
        `   Приоритет: ${task.priority}\n` +
        `   Срок: ${task.dueDate.toISOString().split('T')[0]}`
    )
    .join('\n\n');

  return {
    response: `📋 *Ваши задачи (${userTasks.length}):*\n\n${taskList}\n\nИспользуйте /task_details <ID> для подробной информации`,
    success: true,
  };
}

async function handleAllTasks(user: any): Promise<CommandResult> {
  if (user.role !== 'admin') {
    return {
      response: 'Только администраторы могут просматривать все задачи.',
      success: false,
    };
  }

  const allTasks = await db.select().from(tasks);

  if (allTasks.length === 0) {
    return {
      response: 'Задач пока нет.',
      success: true,
    };
  }

  const taskList = allTasks
    .map(
      (task) =>
        `📌 *ID ${task.id}*: ${task.title}\n` +
        `   Статус: ${task.status}\n` +
        `   Приоритет: ${task.priority}\n` +
        `   Назначена: User #${task.assignedToId}`
    )
    .join('\n\n');

  return {
    response: `📋 *Все задачи (${allTasks.length}):*\n\n${taskList}`,
    success: true,
  };
}

async function handleUpdateStatus(
  user: any,
  args: string
): Promise<CommandResult> {
  const parts = args.trim().split(/\s+/);

  if (parts.length < 2) {
    return {
      response: `Использование: /update_status <ID> <статус>

Статусы:
- pending (ожидает)
- in_progress (в работе)
- completed (завершена)
- rejected (отклонена)

Пример: /update_status 5 in_progress`,
      success: false,
    };
  }

  const taskId = parseInt(parts[0]);
  const newStatus = parts[1].toLowerCase();

  if (isNaN(taskId)) {
    return {
      response: 'ID задачи должен быть числом.',
      success: false,
    };
  }

  const validStatuses = ['pending', 'in_progress', 'completed', 'rejected'];
  if (!validStatuses.includes(newStatus)) {
    return {
      response: `Неверный статус. Допустимые значения: ${validStatuses.join(', ')}`,
      success: false,
    };
  }

  const task = await db
    .select()
    .from(tasks)
    .where(eq(tasks.id, taskId))
    .limit(1)
    .then((rows) => rows[0]);

  if (!task) {
    return {
      response: `Задача с ID ${taskId} не найдена.`,
      success: false,
    };
  }

  if (user.role !== 'admin' && task.assignedToId !== user.id) {
    return {
      response: 'Вы можете обновлять только назначенные вам задачи.',
      success: false,
    };
  }

  await db
    .update(tasks)
    .set({ status: newStatus as any })
    .where(eq(tasks.id, taskId));

  return {
    response: `✅ Статус задачи #${taskId} обновлён на: ${newStatus}`,
    success: true,
  };
}

async function handleTaskDetails(
  user: any,
  args: string
): Promise<CommandResult> {
  const taskId = parseInt(args.trim());

  if (isNaN(taskId)) {
    return {
      response: 'Использование: /task_details <ID>\n\nПример: /task_details 5',
      success: false,
    };
  }

  const task = await db
    .select()
    .from(tasks)
    .where(eq(tasks.id, taskId))
    .limit(1)
    .then((rows) => rows[0]);

  if (!task) {
    return {
      response: `Задача с ID ${taskId} не найдена.`,
      success: false,
    };
  }

  if (user.role !== 'admin' && task.assignedToId !== user.id) {
    return {
      response: 'Вы можете просматривать только назначенные вам задачи.',
      success: false,
    };
  }

  const details = `
📋 *Детали задачи #${task.id}*

*Название:* ${task.title}
*Описание:* ${task.description}
*Статус:* ${task.status}
*Приоритет:* ${task.priority}
*Срок:* ${task.dueDate.toISOString().split('T')[0]}
*Назначена:* User #${task.assignedToId}
*Создана:* ${task.createdAt.toISOString().split('T')[0]}
`;

  return {
    response: details.trim(),
    success: true,
  };
}

function parseTaskParams(args: string): any {
  const params: any = {};

  const titleMatch = args.match(/title:"([^"]*)"/);
  if (titleMatch) params.title = titleMatch[1];

  const descMatch = args.match(/description:"([^"]*)"/);
  if (descMatch) params.description = descMatch[1];

  const priorityMatch = args.match(/priority:(\w+)/);
  if (priorityMatch) params.priority = priorityMatch[1];

  const dueDateMatch = args.match(/due_date:(\d{4}-\d{2}-\d{2})/);
  if (dueDateMatch) params.dueDate = new Date(dueDateMatch[1]);

  const assignedToMatch = args.match(/assigned_to:([^\s]+)/);
  if (assignedToMatch) params.assignedToTelegramId = assignedToMatch[1];

  return params;
}
