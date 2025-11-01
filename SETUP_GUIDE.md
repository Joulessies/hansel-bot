# 🚀 Hansel Bot - Complete Setup Guide

A feature-rich Discord bot similar to Dyno Bot, built with Python and discord.py.

## 📋 Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Bot](#running-the-bot)
- [Deployment](#deployment)
- [Command Reference](#command-reference)

## ✨ Features

### Moderation

- ✅ Ban/Kick/Mute/Unmute members
- ✅ Warning system with tracking
- ✅ Message purging
- ✅ Permission-based command access

### Auto-Moderation

- ✅ Spam detection
- ✅ Profanity filter
- ✅ Link filtering
- ✅ Mass ping detection
- ✅ Whitelisted roles/channels

### Server Management

- ✅ Welcome & goodbye messages
- ✅ Auto-role assignment
- ✅ Custom commands system
- ✅ Reaction roles
- ✅ Scheduled announcements

### User Features

- ✅ AFK system
- ✅ Leveling system with XP
- ✅ Leaderboard

### Logging

- ✅ Message delete/edit logs
- ✅ Member join/leave logs
- ✅ Ban/kick logs
- ✅ Configurable log channels

## 📦 Prerequisites

- Python 3.8 or higher
- Discord Bot Token
- Discord Application ID and Public Key

## 🛠️ Installation

### Step 1: Clone/Download Repository

```bash
# If using git
git clone <repository-url>
cd hansel-bot

# Or download and extract the ZIP file
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Configure Environment

1. Create a `.env` file in the project root:

```env
DISCORD_TOKEN=your_bot_token_here
```

2. Make sure `config.py` has your Application ID and Public Key:

```python
APPLICATION_ID = your_application_id
PUBLIC_KEY = "your_public_key"
```

### Step 4: Enable Discord Intents

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Select your bot application
3. Go to "Bot" section
4. Enable these **Privileged Gateway Intents**:
   - ✅ **MESSAGE CONTENT INTENT** (Required for auto-mod and logging)
   - ✅ **SERVER MEMBERS INTENT** (Required for member events and auto-roles)

### Step 5: Invite Bot to Server

1. Go to OAuth2 → URL Generator in Discord Developer Portal
2. Select scopes:
   - `bot`
   - `applications.commands`
3. Select bot permissions:
   - Administrator (recommended) OR
   - Specific permissions: Manage Roles, Manage Channels, Manage Messages, Ban Members, Kick Members, Moderate Members, Send Messages, Embed Links
4. Copy the generated URL and open it to invite your bot

## ⚙️ Configuration

### Database

The bot uses SQLite database (`bot_data.db`) which is created automatically. All server settings are stored here.

### Initial Setup Commands

After inviting the bot, configure it:

```
/setlogchannel #mod-logs
/setwelcomechannel #welcome
/setgoodbyechannel #goodbye
/setautorole @Member
```

## 🎮 Running the Bot

### Local Development

```bash
python bot_advanced.py
```

### Using the Basic Bot

If you prefer the simpler version:

```bash
python bot.py
```

### Production (with process manager)

Using PM2 (Node.js process manager for Python):

```bash
npm install -g pm2
pm2 start bot_advanced.py --interpreter python3
pm2 save
pm2 startup
```

Or using screen:

```bash
screen -S hansel-bot
python bot_advanced.py
# Press Ctrl+A then D to detach
```

## 🌐 Deployment

### Option 1: Railway

1. Go to [Railway.app](https://railway.app)
2. Create new project
3. Deploy from GitHub or upload files
4. Add environment variable: `DISCORD_TOKEN`
5. Deploy!

### Option 2: Replit

1. Create new Repl
2. Upload all files
3. Set environment variable `DISCORD_TOKEN` in Secrets
4. Run `python bot_advanced.py`

### Option 3: VPS (Ubuntu/Debian)

```bash
# Install Python and pip
sudo apt update
sudo apt install python3 python3-pip git

# Clone repository
git clone <your-repo>
cd hansel-bot

# Install dependencies
pip3 install -r requirements.txt

# Create .env file
nano .env  # Add DISCORD_TOKEN=your_token

# Run with nohup or screen
nohup python3 bot_advanced.py &
```

### Option 4: Heroku

1. Create `Procfile`:

```
worker: python bot_advanced.py
```

2. Deploy using Heroku CLI or GitHub integration
3. Set config vars: `DISCORD_TOKEN`

## 📚 Command Reference

### Moderation Commands

| Command                              | Description        | Permission       |
| ------------------------------------ | ------------------ | ---------------- |
| `/ban <member> [reason]`             | Ban a member       | Ban Members      |
| `/kick <member> [reason]`            | Kick a member      | Kick Members     |
| `/mute <member> [duration] [reason]` | Mute a member      | Moderate Members |
| `/unmute <member>`                   | Unmute a member    | Moderate Members |
| `/warn <member> <reason>`            | Warn a member      | Moderate Members |
| `/warnings <member>`                 | View warnings      | Moderate Members |
| `/clearwarnings <member>`            | Clear all warnings | Administrator    |
| `/purge <amount>`                    | Delete messages    | Manage Messages  |

### Custom Commands

| Command                            | Description              | Permission    |
| ---------------------------------- | ------------------------ | ------------- |
| `/addcommand <command> <response>` | Add custom command       | Administrator |
| `/deletecommand <command>`         | Delete custom command    | Administrator |
| `/listcommands`                    | List all custom commands | Everyone      |

### Configuration Commands

| Command                        | Description         | Permission      |
| ------------------------------ | ------------------- | --------------- |
| `/setautorole [role]`          | Set auto-role       | Manage Roles    |
| `/setlogchannel [channel]`     | Set log channel     | Manage Channels |
| `/setwelcomechannel [channel]` | Set welcome channel | Manage Channels |
| `/setgoodbyechannel [channel]` | Set goodbye channel | Manage Channels |
| `/automod [options]`           | Configure auto-mod  | Administrator   |

### User Commands

| Command           | Description      | Permission |
| ----------------- | ---------------- | ---------- |
| `/afk [message]`  | Set AFK status   | Everyone   |
| `/level [member]` | Check level      | Everyone   |
| `/leaderboard`    | View leaderboard | Everyone   |

### Other Commands

| Command                                                | Description           | Permission    |
| ------------------------------------------------------ | --------------------- | ------------- |
| `/ping`                                                | Check bot latency     | Everyone      |
| `/serverinfo`                                          | Show server info      | Everyone      |
| `/addreactionrole <message_id> <emoji> <role>`         | Add reaction role     | Administrator |
| `/scheduleannouncement <channel> <message> <interval>` | Schedule announcement | Administrator |

## 🔧 Customization

### Auto-Moderation Settings

Edit `PROFANITY_WORDS` in `bot_advanced.py` to add custom words:

```python
PROFANITY_WORDS = ['word1', 'word2', 'word3']
```

Or use database commands to configure per-server.

### XP Rates

Change XP per message in `on_message` event:

```python
result = db.add_xp(message.guild.id, message.author.id, 10)  # Change 10 to desired XP
```

## 📊 Database Schema

The bot uses SQLite with these tables:

- `server_settings` - Server configurations
- `automod_config` - Auto-moderation settings
- `custom_commands` - Custom command storage
- `warnings` - Warning records
- `muted_users` - Mute tracking
- `reaction_roles` - Reaction role mappings
- `user_levels` - Leveling system data
- `afk_users` - AFK status tracking
- `scheduled_announcements` - Repeating announcements
- `message_logs` - Message action logs

## 🐛 Troubleshooting

### Bot doesn't respond to commands

1. Check if intents are enabled in Discord Developer Portal
2. Restart the bot
3. Try `/sync` command (Admin only)

### Auto-moderation not working

1. Ensure MESSAGE CONTENT INTENT is enabled
2. Check bot permissions in channels
3. Verify auto-mod is enabled: `/automod`

### Database errors

1. Check file permissions for `bot_data.db`
2. Ensure SQLite is installed: `python -c "import sqlite3"`

### Commands not syncing

- Global commands can take up to 1 hour
- Use `/sync` for instant guild sync
- Restart Discord client

## 🚀 Scaling Tips

### For Large Servers

1. **Use PostgreSQL instead of SQLite:**

   - Update `database.py` to use `psycopg2`
   - Better performance for high-volume

2. **Add Redis for caching:**

   - Cache command responses
   - Cache leveling data

3. **Implement command cooldowns:**

   - Use `@commands.cooldown()` decorator

4. **Add rate limiting:**

   - Prevent API abuse
   - Limit custom command usage

5. **Use sharding:**
   - For 2500+ servers
   - Modify bot initialization

### Performance Optimization

1. Index database tables on frequently queried columns
2. Use async database operations
3. Cache frequently accessed data
4. Limit message history size for spam detection

## 📝 Notes

- Bot data is stored in `bot_data.db` (SQLite)
- Logs are printed to console
- All commands support both slash (`/`) format
- Configuration persists across restarts
- Custom commands use `!` prefix (e.g., `!mycommand`)

## 🔒 Security

- Never commit `.env` file to version control
- Keep bot token secret
- Use environment variables in production
- Regularly update dependencies
- Review auto-moderation filters

## 📞 Support

For issues or questions:

1. Check console logs for errors
2. Verify bot permissions
3. Ensure all intents are enabled
4. Check Discord API status

## 📄 License

This bot is provided as-is for educational and personal use.

---

**Made with ❤️ using discord.py**
