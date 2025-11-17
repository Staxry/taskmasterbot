import { createStep, createWorkflow } from "../inngest";
import { z } from "zod";
import { handleTelegramCommand } from "../../handlers/telegramCommandHandler";

const processTelegramMessage = createStep({
  id: "process-telegram-message",
  description: "Processes incoming Telegram message using command parser",

  inputSchema: z.object({
    messageText: z.string().describe("User message text from Telegram"),
    telegramId: z.string().describe("Telegram user ID"),
    username: z.string().optional().describe("Telegram username"),
    firstName: z.string().optional().describe("First name"),
    chatId: z.string().describe("Telegram chat ID for sending response"),
    botToken: z.string().describe("Telegram bot token"),
  }),

  outputSchema: z.object({
    response: z.string(),
    success: z.boolean(),
    chatId: z.string(),
    botToken: z.string(),
  }),

  execute: async ({ inputData, mastra }) => {
    const logger = mastra?.getLogger();
    logger?.info('🚀 [processTelegramMessage] Processing command from Telegram user', {
      telegramId: inputData.telegramId,
      command: inputData.messageText,
    });

    if (!inputData.chatId || !inputData.botToken) {
      logger?.error('❌ [processTelegramMessage] Missing required parameters: chatId or botToken');
      return {
        response: 'Ошибка конфигурации: отсутствуют необходимые параметры',
        success: false,
        chatId: inputData.chatId || '',
        botToken: inputData.botToken || '',
      };
    }

    try {
      const result = await handleTelegramCommand({
        telegramId: inputData.telegramId,
        username: inputData.username,
        firstName: inputData.firstName,
        messageText: inputData.messageText,
      });

      logger?.info('✅ [processTelegramMessage] Command processing complete', {
        success: result.success,
      });

      return {
        response: result.response,
        success: result.success,
        chatId: inputData.chatId,
        botToken: inputData.botToken,
      };
    } catch (error) {
      logger?.error('❌ [processTelegramMessage] Command processing failed:', error);
      return {
        response: 'Извините, произошла ошибка при обработке вашей команды. Попробуйте еще раз.',
        success: false,
        chatId: inputData.chatId,
        botToken: inputData.botToken,
      };
    }
  },
});

const sendTelegramResponse = createStep({
  id: "send-telegram-response",
  description: "Sends command response back to Telegram user",

  inputSchema: z.object({
    response: z.string(),
    success: z.boolean(),
    chatId: z.string(),
    botToken: z.string(),
  }),

  outputSchema: z.object({
    sent: z.boolean(),
    message: z.string(),
  }),

  execute: async ({ inputData, mastra }) => {
    const logger = mastra?.getLogger();
    logger?.info('📤 [sendTelegramResponse] Sending response to Telegram', {
      success: inputData.success,
      chatId: inputData.chatId,
    });

    if (!inputData.chatId || !inputData.botToken) {
      logger?.error('❌ [sendTelegramResponse] Missing chatId or botToken');
      return {
        sent: false,
        message: 'Missing required parameters',
      };
    }

    if (!inputData.success) {
      logger?.warn('⚠️ [sendTelegramResponse] Agent processing failed, but still sending error message to user');
    }

    try {
      const response = await fetch(
        `https://api.telegram.org/bot${inputData.botToken}/sendMessage`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            chat_id: inputData.chatId,
            text: inputData.response,
            parse_mode: 'Markdown',
          }),
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        logger?.error('❌ [sendTelegramResponse] Failed to send message:', errorData);
        return {
          sent: false,
          message: `Error: ${errorData.description || 'Unknown error'}`,
        };
      }

      logger?.info('✅ [sendTelegramResponse] Message sent successfully');

      return {
        sent: true,
        message: 'Response sent to Telegram user',
      };
    } catch (error) {
      logger?.error('❌ [sendTelegramResponse] Exception:', error);
      return {
        sent: false,
        message: `Exception: ${error instanceof Error ? error.message : 'Unknown error'}`,
      };
    }
  },
});

export const telegramTaskWorkflow = createWorkflow({
  id: "telegram-task-workflow",

  inputSchema: z.object({
    messageText: z.string().describe("User message text from Telegram"),
    telegramId: z.string().describe("Telegram user ID"),
    username: z.string().optional().describe("Telegram username"),
    firstName: z.string().optional().describe("First name"),
    chatId: z.string().describe("Telegram chat ID for sending response"),
    botToken: z.string().describe("Telegram bot token"),
  }) as any,

  outputSchema: z.object({
    sent: z.boolean(),
    message: z.string(),
  }),
})
  .then(processTelegramMessage as any)
  .then(sendTelegramResponse as any)
  .commit();
