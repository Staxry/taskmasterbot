import type { ContentfulStatusCode } from "hono/utils/http-status";

import { registerApiRoute } from "../mastra/inngest";
import { Mastra } from "@mastra/core";

if (!process.env.TELEGRAM_BOT_TOKEN) {
  console.warn(
    "Trying to initialize Telegram triggers without TELEGRAM_BOT_TOKEN. Can you confirm that the Telegram integration is configured correctly?",
  );
}

export type TriggerInfoTelegramOnNewMessage = {
  type: "telegram/message";
  params: {
    messageText: string;
    telegramId: string;
    chatId: string;
    username?: string;
    firstName?: string;
    lastName?: string;
  };
  payload: any;
};

export function registerTelegramTrigger({
  triggerType,
  handler,
}: {
  triggerType: string;
  handler: (
    mastra: Mastra,
    triggerInfo: TriggerInfoTelegramOnNewMessage,
  ) => Promise<void>;
}) {
  return [
    registerApiRoute("/webhooks/telegram/action", {
      method: "POST",
      handler: async (c) => {
        const mastra = c.get("mastra");
        const logger = mastra.getLogger();
        try {
          const payload = await c.req.json();

          logger?.info("📝 [Telegram] Received webhook payload", {
            hasMessage: !!payload.message,
            messageType: payload.message?.text ? 'text' : 'other',
          });

          if (!payload.message || !payload.message.text) {
            logger?.warn("⚠️ [Telegram] Ignoring non-text message");
            return c.text("OK", 200);
          }

          const message = payload.message;
          const from = message.from;

          await handler(mastra, {
            type: triggerType,
            params: {
              messageText: message.text,
              telegramId: from.id.toString(),
              chatId: message.chat.id.toString(),
              username: from.username,
              firstName: from.first_name,
              lastName: from.last_name,
            },
            payload,
          } as TriggerInfoTelegramOnNewMessage);

          return c.text("OK", 200);
        } catch (error) {
          logger?.error("❌ [Telegram] Error handling webhook:", error);
          return c.text("Internal Server Error", 500);
        }
      },
    }),
  ];
}
