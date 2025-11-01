import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import configuration
from config import APPLICATION_ID, PUBLIC_KEY

# Bot setup
intents = discord.Intents.default()
# Uncomment these if you've enabled privileged intents in Discord Developer Portal
# intents.message_content = True  # Required for prefix commands (!ping, etc.)
# intents.members = True  # Required for member information

bot = commands.Bot(command_prefix='!', intents=intents, application_id=APPLICATION_ID)
tree = bot.tree  # Slash command tree


@bot.event
async def on_ready():
    """Called when the bot is ready and connected to Discord."""
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guild(s)')
    
    # Sync slash commands
    try:
        synced = await tree.sync()
        print(f'Synced {len(synced)} slash command(s)')
    except Exception as e:
        print(f'Failed to sync slash commands: {e}')
    
    # Set bot status
    await bot.change_presence(
        activity=discord.Game(name="Use /help or !help for commands")
    )


@bot.event
async def on_command_error(ctx, error):
    """Handle command errors."""
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Command not found. Use `!help` to see available commands.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Missing required arguments. Please check the command usage.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to use this command.")
    else:
        await ctx.send(f"An error occurred: {str(error)}")
        print(f"Error: {error}")


@bot.command(name='ping', help='Check if the bot is responsive')
async def ping(ctx):
    """Respond with the bot's latency."""
    latency = round(bot.latency * 1000)
    await ctx.send(f'Pong! Latency: {latency}ms')


@bot.command(name='hello', help='Greet the bot')
async def hello(ctx):
    """Greet the user."""
    await ctx.send(f'Hello, {ctx.author.mention}!')


@bot.command(name='server', help='Display server information')
async def server_info(ctx):
    """Display information about the server."""
    guild = ctx.guild
    try:
        owner_mention = guild.owner.mention if guild.owner else "Unknown"
    except:
        owner_mention = "Unknown (Enable Members Intent for owner info)"
    
    embed = discord.Embed(
        title=f"Server: {guild.name}",
        description=f"Members: {guild.member_count}",
        color=discord.Color.blue()
    )
    embed.add_field(name="Owner", value=owner_mention, inline=True)
    embed.add_field(name="Created", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="Region", value=str(guild.region) if hasattr(guild, 'region') else "N/A", inline=True)
    await ctx.send(embed=embed)


@bot.command(name='clear', help='Clear messages (requires Manage Messages permission)')
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int = 5):
    """Clear a specified number of messages."""
    if amount > 100:
        await ctx.send("You can only clear up to 100 messages at once.")
        return
    
    await ctx.channel.purge(limit=amount + 1)  # +1 to include the command message
    message = await ctx.send(f"Cleared {amount} message(s).")
    await message.delete(delay=3)


@bot.command(name='kick', help='Kick a member (requires Kick Members permission)')
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason=None):
    """Kick a member from the server."""
    if member == ctx.author:
        await ctx.send("You cannot kick yourself!")
        return
    
    try:
        await member.kick(reason=reason)
        await ctx.send(f'{member.mention} has been kicked. Reason: {reason or "No reason provided"}')
    except discord.Forbidden:
        await ctx.send("I don't have permission to kick this member.")


@bot.command(name='ban', help='Ban a member (requires Ban Members permission)')
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason=None):
    """Ban a member from the server."""
    if member == ctx.author:
        await ctx.send("You cannot ban yourself!")
        return
    
    try:
        await member.ban(reason=reason)
        await ctx.send(f'{member.mention} has been banned. Reason: {reason or "No reason provided"}')
    except discord.Forbidden:
        await ctx.send("I don't have permission to ban this member.")


# Slash Commands (Application Commands)
@tree.command(name="ping", description="Check if the bot is responsive")
async def slash_ping(interaction: discord.Interaction):
    """Respond with the bot's latency."""
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f'Pong! Latency: {latency}ms')


@tree.command(name="hello", description="Greet the bot")
async def slash_hello(interaction: discord.Interaction):
    """Greet the user."""
    await interaction.response.send_message(f'Hello, {interaction.user.mention}!')


@tree.command(name="server", description="Display server information")
async def slash_server(interaction: discord.Interaction):
    """Display information about the server."""
    guild = interaction.guild
    embed = discord.Embed(
        title=f"Server: {guild.name}",
        description=f"Members: {guild.member_count}",
        color=discord.Color.blue()
    )
    embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
    embed.add_field(name="Created", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="Region", value=str(guild.region) if hasattr(guild, 'region') else "N/A", inline=True)
    await interaction.response.send_message(embed=embed)


@tree.command(name="clear", description="Clear messages (requires Manage Messages permission)")
@app_commands.describe(amount="Number of messages to clear (1-100)")
@app_commands.default_permissions(manage_messages=True)
async def slash_clear(interaction: discord.Interaction, amount: int = 5):
    """Clear a specified number of messages."""
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    if amount > 100:
        await interaction.response.send_message("You can only clear up to 100 messages at once.", ephemeral=True)
        return
    
    if amount < 1:
        await interaction.response.send_message("Amount must be at least 1.", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"Cleared {len(deleted)} message(s).", ephemeral=True)


# Run the bot
if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("Error: DISCORD_TOKEN not found in environment variables!")
        print("Please create a .env file with your Discord bot token.")
    else:
        bot.run(token)

