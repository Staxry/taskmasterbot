import { createTool } from "@mastra/core/tools";
import { z } from "zod";

export const sendTelegramMessageTool = createTool({
  id: "send-telegram-message",
  description: "Sends a message to a Telegram user",
  
  inputSchema: z.object({
    telegramId: z.string().describe("Telegram user ID to send message to"),
    message: z.string().describe("Message text to send"),
    botToken: z.string().describe("Telegram bot token"),
  }),
  
  outputSchema: z.object({
    success: z.boolean(),
    message: z.string(),
  }),
  
  execute: async ({ context, mastra }) => {
    const logger = mastra?.getLogger();
    logger?.info('🔧 [sendTelegramMessageTool] Executing with:', { 
      telegramId: context.telegramId,
      messageLength: context.message.length,
    });
    
    try {
      const response = await fetch(
        `https://api.telegram.org/bot${context.botToken}/sendMessage`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            chat_id: context.telegramId,
            text: context.message,
            parse_mode: 'Markdown',
          }),
        }
      );
      
      if (!response.ok) {
        const errorData = await response.json();
        logger?.error('❌ [sendTelegramMessageTool] Failed to send message:', errorData);
        return {
          success: false,
          message: `Ошибка отправки сообщения: ${errorData.description || 'Unknown error'}`,
        };
      }
      
      logger?.info('✅ [sendTelegramMessageTool] Message sent successfully');
      
      return {
        success: true,
        message: 'Сообщение отправлено успешно',
      };
    } catch (error) {
      logger?.error('❌ [sendTelegramMessageTool] Error sending message:', error);
      return {
        success: false,
        message: `Ошибка: ${error instanceof Error ? error.message : 'Unknown error'}`,
      };
    }
  },
});
