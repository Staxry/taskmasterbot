import { createTool } from "@mastra/core/tools";
import { z } from "zod";
import { db } from "../../../shared/db";
import { tasks, users } from "../../../shared/schema";
import { eq, and, gte, lte, sql } from "drizzle-orm";

export const createTaskTool = createTool({
  id: "create-task",
  description: "Creates a new task and assigns it to an employee",
  
  inputSchema: z.object({
    title: z.string().describe("Task title"),
    description: z.string().describe("Detailed task description"),
    priority: z.enum(['low', 'medium', 'high', 'urgent']).describe("Task priority level"),
    dueDate: z.string().describe("Due date in ISO format (YYYY-MM-DD or full ISO timestamp)"),
    assignedToTelegramId: z.string().describe("Telegram ID of employee to assign task to"),
    createdByUserId: z.number().describe("Database ID of admin creating the task"),
  }),
  
  outputSchema: z.object({
    success: z.boolean(),
    taskId: z.number().optional(),
    message: z.string(),
    assignedToTelegramId: z.string().optional(),
  }),
  
  execute: async ({ context, mastra }) => {
    const logger = mastra?.getLogger();
    logger?.info('🔧 [createTaskTool] Executing with:', context);
    
    const assignedUsers = await db
      .select()
      .from(users)
      .where(eq(users.telegramId, context.assignedToTelegramId))
      .limit(1);
    
    if (assignedUsers.length === 0) {
      logger?.error('❌ [createTaskTool] Employee not found:', { telegramId: context.assignedToTelegramId });
      return {
        success: false,
        message: `Сотрудник с Telegram ID ${context.assignedToTelegramId} не найден`,
      };
    }
    
    const assignedUser = assignedUsers[0];
    
    const newTasks = await db
      .insert(tasks)
      .values({
        title: context.title,
        description: context.description,
        priority: context.priority,
        dueDate: new Date(context.dueDate),
        assignedToId: assignedUser.id,
        createdById: context.createdByUserId,
        status: 'pending',
      })
      .returning();
    
    const newTask = newTasks[0];
    logger?.info('✅ [createTaskTool] Created task successfully:', { taskId: newTask.id });
    
    return {
      success: true,
      taskId: newTask.id,
      message: `Задача "${context.title}" создана и назначена сотруднику`,
      assignedToTelegramId: context.assignedToTelegramId,
    };
  },
});

export const updateTaskStatusTool = createTool({
  id: "update-task-status",
  description: "Updates task status (pending, in_progress, completed, rejected)",
  
  inputSchema: z.object({
    taskId: z.number().describe("Task database ID"),
    status: z.enum(['pending', 'in_progress', 'completed', 'rejected']).describe("New task status"),
    userId: z.number().describe("User ID making the update"),
  }),
  
  outputSchema: z.object({
    success: z.boolean(),
    message: z.string(),
  }),
  
  execute: async ({ context, mastra }) => {
    const logger = mastra?.getLogger();
    logger?.info('🔧 [updateTaskStatusTool] Executing with:', context);
    
    const existingTasks = await db
      .select()
      .from(tasks)
      .where(eq(tasks.id, context.taskId))
      .limit(1);
    
    if (existingTasks.length === 0) {
      return {
        success: false,
        message: 'Задача не найдена',
      };
    }
    
    const updateData: any = {
      status: context.status,
      updatedAt: new Date(),
    };
    
    if (context.status === 'completed') {
      updateData.completedAt = new Date();
    }
    
    await db
      .update(tasks)
      .set(updateData)
      .where(eq(tasks.id, context.taskId));
    
    logger?.info('✅ [updateTaskStatusTool] Updated task status successfully');
    
    const statusMessages: Record<string, string> = {
      pending: 'в ожидании',
      in_progress: 'в работе',
      completed: 'завершена',
      rejected: 'отклонена',
    };
    
    return {
      success: true,
      message: `Статус задачи изменен на: ${statusMessages[context.status]}`,
    };
  },
});

export const getUserTasksTool = createTool({
  id: "get-user-tasks",
  description: "Gets all tasks assigned to a specific user",
  
  inputSchema: z.object({
    userId: z.number().describe("User database ID"),
    status: z.enum(['pending', 'in_progress', 'completed', 'rejected', 'all']).optional().describe("Filter by status"),
  }),
  
  outputSchema: z.object({
    tasks: z.array(z.object({
      id: z.number(),
      title: z.string(),
      description: z.string(),
      priority: z.enum(['low', 'medium', 'high', 'urgent']),
      status: z.enum(['pending', 'in_progress', 'completed', 'rejected']),
      dueDate: z.string(),
      createdAt: z.string(),
      completedAt: z.string().nullable(),
    })),
  }),
  
  execute: async ({ context, mastra }) => {
    const logger = mastra?.getLogger();
    logger?.info('🔧 [getUserTasksTool] Executing with:', context);
    
    let query = db
      .select()
      .from(tasks)
      .where(eq(tasks.assignedToId, context.userId));
    
    const tasksList = await query;
    
    const filteredTasks = context.status && context.status !== 'all' 
      ? tasksList.filter(t => t.status === context.status)
      : tasksList;
    
    logger?.info('✅ [getUserTasksTool] Found tasks:', { count: filteredTasks.length });
    
    return {
      tasks: filteredTasks.map(t => ({
        id: t.id,
        title: t.title,
        description: t.description,
        priority: t.priority,
        status: t.status,
        dueDate: t.dueDate.toISOString(),
        createdAt: t.createdAt.toISOString(),
        completedAt: t.completedAt?.toISOString() || null,
      })),
    };
  },
});

export const getAllTasksTool = createTool({
  id: "get-all-tasks",
  description: "Gets all tasks with filtering by status and date range (admin only)",
  
  inputSchema: z.object({
    status: z.enum(['pending', 'in_progress', 'completed', 'rejected', 'all']).optional().describe("Filter by status"),
    startDate: z.string().optional().describe("Filter tasks created after this date (ISO format)"),
    endDate: z.string().optional().describe("Filter tasks created before this date (ISO format)"),
  }),
  
  outputSchema: z.object({
    tasks: z.array(z.object({
      id: z.number(),
      title: z.string(),
      description: z.string(),
      priority: z.enum(['low', 'medium', 'high', 'urgent']),
      status: z.enum(['pending', 'in_progress', 'completed', 'rejected']),
      dueDate: z.string(),
      assignedToTelegramId: z.string(),
      createdAt: z.string(),
      completedAt: z.string().nullable(),
    })),
    totalCount: z.number(),
  }),
  
  execute: async ({ context, mastra }) => {
    const logger = mastra?.getLogger();
    logger?.info('🔧 [getAllTasksTool] Executing with:', context);
    
    const tasksList = await db
      .select({
        task: tasks,
        assignedUser: users,
      })
      .from(tasks)
      .leftJoin(users, eq(tasks.assignedToId, users.id));
    
    let filteredTasks = tasksList;
    
    if (context.status && context.status !== 'all') {
      filteredTasks = filteredTasks.filter(t => t.task.status === context.status);
    }
    
    if (context.startDate) {
      const startDate = new Date(context.startDate);
      filteredTasks = filteredTasks.filter(t => t.task.createdAt >= startDate);
    }
    
    if (context.endDate) {
      const endDate = new Date(context.endDate);
      filteredTasks = filteredTasks.filter(t => t.task.createdAt <= endDate);
    }
    
    logger?.info('✅ [getAllTasksTool] Found tasks:', { count: filteredTasks.length });
    
    return {
      tasks: filteredTasks.map(t => ({
        id: t.task.id,
        title: t.task.title,
        description: t.task.description,
        priority: t.task.priority,
        status: t.task.status,
        dueDate: t.task.dueDate.toISOString(),
        assignedToTelegramId: t.assignedUser?.telegramId || '',
        createdAt: t.task.createdAt.toISOString(),
        completedAt: t.task.completedAt?.toISOString() || null,
      })),
      totalCount: filteredTasks.length,
    };
  },
});

export const getTaskByIdTool = createTool({
  id: "get-task-by-id",
  description: "Gets a specific task by ID with full details",
  
  inputSchema: z.object({
    taskId: z.number().describe("Task database ID"),
  }),
  
  outputSchema: z.object({
    success: z.boolean(),
    task: z.object({
      id: z.number(),
      title: z.string(),
      description: z.string(),
      priority: z.enum(['low', 'medium', 'high', 'urgent']),
      status: z.enum(['pending', 'in_progress', 'completed', 'rejected']),
      dueDate: z.string(),
      assignedToTelegramId: z.string(),
      createdAt: z.string(),
      completedAt: z.string().nullable(),
    }).optional(),
    message: z.string(),
  }),
  
  execute: async ({ context, mastra }) => {
    const logger = mastra?.getLogger();
    logger?.info('🔧 [getTaskByIdTool] Executing with:', context);
    
    const taskData = await db
      .select({
        task: tasks,
        assignedUser: users,
      })
      .from(tasks)
      .leftJoin(users, eq(tasks.assignedToId, users.id))
      .where(eq(tasks.id, context.taskId))
      .limit(1);
    
    if (taskData.length === 0) {
      return {
        success: false,
        message: 'Задача не найдена',
      };
    }
    
    const data = taskData[0];
    logger?.info('✅ [getTaskByIdTool] Found task:', { taskId: data.task.id });
    
    return {
      success: true,
      task: {
        id: data.task.id,
        title: data.task.title,
        description: data.task.description,
        priority: data.task.priority,
        status: data.task.status,
        dueDate: data.task.dueDate.toISOString(),
        assignedToTelegramId: data.assignedUser?.telegramId || '',
        createdAt: data.task.createdAt.toISOString(),
        completedAt: data.task.completedAt?.toISOString() || null,
      },
      message: 'Задача найдена',
    };
  },
});
