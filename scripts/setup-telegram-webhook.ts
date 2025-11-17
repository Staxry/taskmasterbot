import * as dotenv from 'dotenv';

dotenv.config();

const TELEGRAM_BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;

if (!TELEGRAM_BOT_TOKEN) {
  console.error('❌ TELEGRAM_BOT_TOKEN not found in environment variables');
  process.exit(1);
}

async function setupWebhook() {
  let webhookUrl: string;
  
  if (process.env.REPLIT_DOMAINS) {
    const domain = process.env.REPLIT_DOMAINS.split(',')[0];
    webhookUrl = `https://${domain}/webhooks/telegram/action`;
  } else {
    console.error('❌ REPLIT_DOMAINS not found. This script should be run on Replit.');
    console.log('ℹ️  For local testing, you can use ngrok or similar service.');
    process.exit(1);
  }

  console.log(`📡 Setting up Telegram webhook...`);
  console.log(`🔗 Webhook URL: ${webhookUrl}`);

  try {
    const response = await fetch(
      `https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          url: webhookUrl,
          allowed_updates: ['message'],
        }),
      }
    );

    const data = await response.json();

    if (data.ok) {
      console.log('✅ Webhook successfully set up!');
      console.log('📝 Response:', data.description);
    } else {
      console.error('❌ Failed to set up webhook:', data.description);
      process.exit(1);
    }

    const infoResponse = await fetch(
      `https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo`
    );
    const infoData = await infoResponse.json();
    
    console.log('\n📊 Webhook Info:');
    console.log('   URL:', infoData.result.url);
    console.log('   Pending updates:', infoData.result.pending_update_count);
    console.log('   Last error:', infoData.result.last_error_message || 'None');
    
  } catch (error) {
    console.error('❌ Error setting up webhook:', error);
    process.exit(1);
  }
}

setupWebhook();
