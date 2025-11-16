import { createStep, createWorkflow } from "../inngest";
import { z } from "zod";
import { telegramTaskAgent } from "../agents/telegramTaskAgent";

const processTelegramMessage = createStep({
  id: "process-telegram-message",
  description: "Processes incoming Telegram message with AI agent and sends response back",

  inputSchema: z.object({
    threadId: z.string().describe("Thread ID for conversation memory"),
    messageText: z.string().describe("User message text from Telegram"),
    telegramId: z.string().describe("Telegram user ID"),
    username: z.string().optional().describe("Telegram username"),
    firstName: z.string().optional().describe("First name"),
    lastName: z.string().optional().describe("Last name"),
    chatId: z.string().describe("Telegram chat ID for sending response"),
    botToken: z.string().describe("Telegram bot token"),
  }),

  outputSchema: z.object({
    response: z.string(),
    success: z.boolean(),
  }),

  execute: async ({ inputData, mastra }) => {
    const logger = mastra?.getLogger();
    logger?.info('🚀 [processTelegramMessage] Processing message from Telegram user', {
      telegramId: inputData.telegramId,
      messageLength: inputData.messageText.length,
    });

    const prompt = `
Пользователь написал: "${inputData.messageText}"

Telegram ID пользователя: ${inputData.telegramId}
Имя: ${inputData.firstName || 'N/A'}
Username: ${inputData.username || 'N/A'}

Обработайте запрос пользователя:
1. Сначала получите или создайте пользователя в базе данных
2. Проверьте его роль (админ или сотрудник)
3. Выполните запрошенное действие в соответствии с ролью
4. Если это новый пользователь, поприветствуйте его и объясните возможности бота
5. Предоставьте четкий и полезный ответ на русском языке
`;

    const response = await telegramTaskAgent.generateLegacy(
      [{ role: "user", content: prompt }],
      {
        resourceId: "telegram-bot",
        threadId: inputData.threadId,
      }
    );

    logger?.info('✅ [processTelegramMessage] Agent processing complete');

    return {
      response: response.text,
      success: true,
    };
  },
});

const sendTelegramResponse = createStep({
  id: "send-telegram-response",
  description: "Sends AI agent response back to Telegram user",

  inputSchema: z.object({
    response: z.string(),
    success: z.boolean(),
    chatId: z.string().optional(),
    botToken: z.string().optional(),
  }),

  outputSchema: z.object({
    sent: z.boolean(),
    message: z.string(),
  }),

  execute: async ({ inputData, mastra }) => {
    const logger = mastra?.getLogger();
    logger?.info('📤 [sendTelegramResponse] Sending response to Telegram');

    if (!inputData.chatId || !inputData.botToken) {
      logger?.error('❌ [sendTelegramResponse] Missing chatId or botToken');
      return {
        sent: false,
        message: 'Missing required parameters',
      };
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
    threadId: z.string().describe("Thread ID for conversation memory"),
    messageText: z.string().describe("User message text from Telegram"),
    telegramId: z.string().describe("Telegram user ID"),
    username: z.string().optional().describe("Telegram username"),
    firstName: z.string().optional().describe("First name"),
    lastName: z.string().optional().describe("Last name"),
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
