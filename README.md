# Discord Bot

A Discord bot built with Python using discord.py.

## Features

- **Basic Commands**: Ping, Hello, Server Info
- **Slash Commands**: Modern Discord slash command support
- **Prefix Commands**: Traditional `!` prefix commands
- **Moderation**: Clear messages, Kick, Ban members
- **Error Handling**: Comprehensive error handling for commands
- **Customizable**: Easy to extend with new commands

## Setup

### Prerequisites

- Python 3.8 or higher
- A Discord account
- A Discord bot token

### Getting a Discord Bot Token

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Go to the "Bot" section and click "Add Bot"
4. Under "Token", click "Copy" to get your bot token
5. Enable the following Privileged Gateway Intents (if needed):
   - Message Content Intent
   - Server Members Intent
6. Under "OAuth2" > "URL Generator", select:
   - Scopes: `bot`
   - Bot Permissions: Select permissions you want (e.g., Manage Messages, Kick Members, Ban Members)
7. Copy the generated URL and open it in your browser to invite the bot to your server

### Installation

1. Clone or download this repository

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file:

```bash
cp .env.example .env
```

4. Edit `.env` and add your Discord bot token:

```
DISCORD_TOKEN=your_actual_bot_token_here
```

**Note**: The Application ID and Public Key are already configured in `config.py`. If you need to change them, edit that file.

5. Run the bot:

```bash
python bot.py
```

## Commands

### Slash Commands (Application Commands)

- `/ping` - Check if the bot is responsive
- `/hello` - Greet the bot
- `/server` - Display server information
- `/clear [amount]` - Clear messages (requires Manage Messages permission)

### Prefix Commands

- `!ping` - Check if the bot is responsive
- `!hello` - Greet the bot
- `!server` - Display server information
- `!clear [amount]` - Clear messages (requires Manage Messages permission)
- `!kick @member [reason]` - Kick a member (requires Kick Members permission)
- `!ban @member [reason]` - Ban a member (requires Ban Members permission)
- `!help` - Show all available commands

## Extending the Bot

To add new commands, simply add new functions with the `@bot.command()` decorator:

```python
@bot.command(name='mycommand', help='Description of the command')
async def mycommand(ctx, arg1, arg2=None):
    await ctx.send(f'Command executed with {arg1} and {arg2}')
```

## Notes

- Make sure your bot has the necessary permissions in the server
- Keep your bot token secret and never commit it to version control
- For production use, consider using environment variables or a secrets manager
# hansel-bot
