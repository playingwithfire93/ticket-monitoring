# Notification Configuration Guide

## Overview
Your ticket monitoring system can now send suggestion notifications via:
1. **Email** - Send to your email address
2. **Multiple Telegram Groups** - Send to different Telegram chats/groups
3. **WhatsApp** - Existing functionality

## Email Setup

### For Gmail:
1. Enable 2-Factor Authentication on your Gmail account
2. Generate an App Password:
   - Go to Google Account settings
   - Security → 2-Step Verification → App passwords
   - Generate password for "Mail"
3. Add to your `.env` file:
```
SENDER_EMAIL=your_email@gmail.com
SENDER_PASSWORD=your_generated_app_password
RECIPIENT_EMAIL=admin@yourdomain.com
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
```

### For Other Email Providers:
- **Outlook/Hotmail**: `smtp-mail.outlook.com`, port `587`
- **Yahoo**: `smtp.mail.yahoo.com`, port `587`
- **Custom SMTP**: Configure accordingly

## Telegram Setup

### Main Bot (existing):
```
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_main_chat_id
```

### Admin Group (new - optional):
```
ADMIN_TELEGRAM_CHAT_ID=your_admin_group_chat_id
```

### How to get Chat IDs:
1. Add your bot to the group
2. Send a message to the group
3. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Look for the `chat.id` in the response

## Testing
After configuring, submit a test suggestion through your dashboard to verify notifications are working.

## Troubleshooting

### Email Issues:
- **Authentication Error**: Check if 2FA is enabled and you're using an app password
- **SMTP Error**: Verify SMTP server and port settings
- **Timeout**: Check firewall/antivirus blocking SMTP connections

### Telegram Issues:
- **Bot Not Responding**: Ensure bot token is correct
- **Permission Denied**: Make sure bot is admin in the group (if required)
- **Wrong Chat ID**: Double-check the chat ID format (can be negative for groups)
