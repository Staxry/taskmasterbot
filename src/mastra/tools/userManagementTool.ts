import { createTool } from "@mastra/core/tools";
import { z } from "zod";
import { db } from "../../../shared/db";
import { users } from "../../../shared/schema";
import { eq } from "drizzle-orm";

export const getUserOrCreateTool = createTool({
  id: "get-or-create-user",
  description: "Gets existing user or creates new user by Telegram ID",
  
  inputSchema: z.object({
    telegramId: z.string().describe("Telegram user ID"),
    username: z.string().optional().describe("Telegram username"),
    firstName: z.string().optional().describe("User first name"),
    lastName: z.string().optional().describe("User last name"),
  }),
  
  outputSchema: z.object({
    id: z.number(),
    telegramId: z.string(),
    username: z.string().nullable(),
    firstName: z.string().nullable(),
    lastName: z.string().nullable(),
    role: z.enum(['admin', 'employee']),
    isNewUser: z.boolean(),
  }),
  
  execute: async ({ context, mastra }) => {
    const logger = mastra?.getLogger();
    logger?.info('🔧 [getUserOrCreateTool] Executing with:', context);
    
    const existingUsers = await db
      .select()
      .from(users)
      .where(eq(users.telegramId, context.telegramId))
      .limit(1);
    
    if (existingUsers.length > 0) {
      const user = existingUsers[0];
      logger?.info('✅ [getUserOrCreateTool] Found existing user:', { userId: user.id });
      return {
        id: user.id,
        telegramId: user.telegramId,
        username: user.username,
        firstName: user.firstName,
        lastName: user.lastName,
        role: user.role,
        isNewUser: false,
      };
    }
    
    const newUsers = await db
      .insert(users)
      .values({
        telegramId: context.telegramId,
        username: context.username || null,
        firstName: context.firstName || null,
        lastName: context.lastName || null,
        role: 'employee',
      })
      .returning();
    
    const newUser = newUsers[0];
    logger?.info('✅ [getUserOrCreateTool] Created new user:', { userId: newUser.id });
    
    return {
      id: newUser.id,
      telegramId: newUser.telegramId,
      username: newUser.username,
      firstName: newUser.firstName,
      lastName: newUser.lastName,
      role: newUser.role,
      isNewUser: true,
    };
  },
});

export const updateUserRoleTool = createTool({
  id: "update-user-role",
  description: "Updates user role (admin/employee)",
  
  inputSchema: z.object({
    userId: z.number().describe("User database ID"),
    role: z.enum(['admin', 'employee']).describe("New role for the user"),
  }),
  
  outputSchema: z.object({
    success: z.boolean(),
    message: z.string(),
  }),
  
  execute: async ({ context, mastra }) => {
    const logger = mastra?.getLogger();
    logger?.info('🔧 [updateUserRoleTool] Executing with:', context);
    
    await db
      .update(users)
      .set({ role: context.role, updatedAt: new Date() })
      .where(eq(users.id, context.userId));
    
    logger?.info('✅ [updateUserRoleTool] Updated user role successfully');
    
    return {
      success: true,
      message: `User role updated to ${context.role}`,
    };
  },
});

export const getUsersByRoleTool = createTool({
  id: "get-users-by-role",
  description: "Gets all users with specific role",
  
  inputSchema: z.object({
    role: z.enum(['admin', 'employee']).describe("Role to filter by"),
  }),
  
  outputSchema: z.object({
    users: z.array(z.object({
      id: z.number(),
      telegramId: z.string(),
      username: z.string().nullable(),
      firstName: z.string().nullable(),
      lastName: z.string().nullable(),
      role: z.enum(['admin', 'employee']),
    })),
  }),
  
  execute: async ({ context, mastra }) => {
    const logger = mastra?.getLogger();
    logger?.info('🔧 [getUsersByRoleTool] Executing with:', context);
    
    const usersList = await db
      .select()
      .from(users)
      .where(eq(users.role, context.role));
    
    logger?.info('✅ [getUsersByRoleTool] Found users:', { count: usersList.length });
    
    return {
      users: usersList.map(u => ({
        id: u.id,
        telegramId: u.telegramId,
        username: u.username,
        firstName: u.firstName,
        lastName: u.lastName,
        role: u.role,
      })),
    };
  },
});
