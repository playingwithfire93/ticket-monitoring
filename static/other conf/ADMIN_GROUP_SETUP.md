# Admin Telegram Group Setup

## Overview
Your ticket monitoring system now supports:
- **Main Telegram Group**: For ticket change notifications (existing)
- **Admin Telegram Group**: For website suggestions (new)

## Setup Steps

### 1. Create Admin Telegram Group
1. Create a new Telegram group for admin notifications
2. Add your bot to the admin group
3. Make sure the bot has permission to send messages

### 2. Get the Admin Group Chat ID
1. Send a message in the admin group (like "Hello admin bot!")
2. Visit this URL in your browser:
   ```
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   ```
3. Look for your message in the response
4. Find the `chat.id` value (usually negative for groups, like `-1001234567890`)

### 3. Update Your .env File
Add this line to your `.env` file:
```
ADMIN_TELEGRAM_CHAT_ID=-1001234567890
```
Replace `-1001234567890` with your actual admin group chat ID.

### 4. Your Complete .env Configuration
```
# Main bot settings (existing)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_main_chat_id

# Admin group for suggestions (new)
ADMIN_TELEGRAM_CHAT_ID=your_admin_group_chat_id

# Other settings...
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_token
```

## How It Works

### Main Group (TELEGRAM_CHAT_ID)
- Gets notifications when ticket websites change
- For regular users who want to know about ticket updates

### Admin Group (ADMIN_TELEGRAM_CHAT_ID)
- Gets notifications when someone submits a website suggestion
- Only for admins who need to review new site suggestions
- Messages include the suggested site name, URL, and reason

## Testing
1. Submit a test suggestion through your dashboard
2. Check that the notification appears in your admin group
3. Main group should NOT receive suggestion notifications

## Benefits
- **Clean separation**: Users get ticket updates, admins get suggestions
- **No email needed**: Everything stays in Telegram
- **Easy management**: Different groups for different purposes
- **Optional**: If you don't set ADMIN_TELEGRAM_CHAT_ID, suggestions just won't send notifications (but still save to file)
