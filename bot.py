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
intents.message_content = True  # Required for prefix commands (!ping, etc.) and logging
intents.members = True  # Required for member join events and member information

bot = commands.Bot(command_prefix='!', intents=intents, application_id=APPLICATION_ID)
tree = bot.tree  # Slash command tree


@bot.event
async def on_ready():
    """Called when the bot is ready and connected to Discord."""
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot ID: {bot.user.id}')
    print(f'Bot is in {len(bot.guilds)} guild(s)')
    
    # List all servers
    if bot.guilds:
        print("\nServers the bot is in:")
        for guild in bot.guilds:
            print(f"  - {guild.name} (ID: {guild.id})")
    
    # Sync slash commands
    print("\nSyncing slash commands...")
    try:
        # First sync globally
        synced = await tree.sync()
        print(f'✓ Synced {len(synced)} global slash command(s)')
        if synced:
            print("Global Commands:")
            for cmd in synced:
                print(f"  - /{cmd.name}")
        
        # Copy global commands to each guild for instant availability
        for guild in bot.guilds:
            try:
                tree.copy_global_to(guild=guild)
                guild_synced = await tree.sync(guild=guild)
                print(f'✓ Synced {len(guild_synced)} command(s) to {guild.name} (instant)')
            except Exception as e:
                print(f'✗ Failed to sync to {guild.name}: {e}')
    except Exception as e:
        print(f'✗ Failed to sync slash commands: {e}')
        print("Note: It may take a few minutes for slash commands to appear in Discord")
    
    # Set bot status
    await bot.change_presence(
        activity=discord.Game(name="Use /help or !help for commands")
    )
    
    print("\nBot is ready! Try using /ping in your server.")


# Server Configuration Storage (in production, use a database)
server_configs = {}  # Format: {guild_id: {'autorole': role_id, 'log_channel': channel_id, 'suggestion_channel': channel_id}}

def get_config(guild_id):
    """Get server configuration or create default."""
    if guild_id not in server_configs:
        server_configs[guild_id] = {
            'autorole': None,
            'log_channel': None,
            'suggestion_channel': None,
            'welcome_channel_id': None,
            'goodbye_channel_id': None
        }
    return server_configs[guild_id]


@bot.event
async def on_member_join(member: discord.Member):
    """Called when a member joins the server."""
    guild = member.guild
    config = get_config(guild.id)
    
    # Auto-role assignment
    if config['autorole']:
        try:
            role = guild.get_role(config['autorole'])
            if role and guild.me.guild_permissions.manage_roles and role < guild.me.top_role:
                await member.add_roles(role, reason="Auto-role on join")
                print(f"Assigned auto-role {role.name} to {member.name}")
        except Exception as e:
            print(f"Error assigning auto-role: {e}")
    
    # Welcome message - only send if welcome channel is configured
    # To set welcome channel, use: /setwelcomechannel #announcements
    channel = None
    welcome_channel_id = config.get('welcome_channel_id')
    
    if welcome_channel_id:
        channel = guild.get_channel(welcome_channel_id)
    
    # If no channel configured, don't send welcome message
    if not channel:
        return
    
    if channel:
        embed = discord.Embed(
            title="🎉 Welcome to the Server!",
            description=f"Welcome {member.mention} to **{guild.name}**!",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(
            name="Member Count",
            value=f"You are member #{guild.member_count}",
            inline=True
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="We're glad to have you here!")
        
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            print(f"Could not send welcome message to {channel.name} - missing permissions")
        except Exception as e:
            print(f"Error sending welcome message: {e}")


@bot.event
async def on_member_remove(member: discord.Member):
    """Called when a member leaves the server."""
    guild = member.guild
    config = get_config(guild.id)
    
    # Only send goodbye message if channel is configured
    goodbye_channel_id = config.get('goodbye_channel_id')
    if not goodbye_channel_id:
        return
    
    channel = guild.get_channel(goodbye_channel_id)
    if not channel:
        return
    
    if channel:
        embed = discord.Embed(
            title="👋 Member Left",
            description=f"{member.display_name} ({member}) has left the server.",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Member Count", value=f"Now {guild.member_count} members", inline=True)
        
        try:
            await channel.send(embed=embed)
        except Exception as e:
            print(f"Error sending leave message: {e}")


@bot.event
async def on_message_delete(message: discord.Message):
    """Log deleted messages."""
    if message.author.bot:
        return
    
    config = get_config(message.guild.id)
    log_channel_id = config.get('log_channel')
    
    if not log_channel_id:
        return
    
    log_channel = message.guild.get_channel(log_channel_id)
    if not log_channel:
        return
    
    embed = discord.Embed(
        title="🗑️ Message Deleted",
        color=discord.Color.red(),
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="Author", value=f"{message.author.mention} ({message.author})", inline=False)
    embed.add_field(name="Channel", value=message.channel.mention, inline=True)
    
    if message.content:
        content = message.content[:1024]  # Discord embed limit
        embed.add_field(name="Content", value=content or "*No content*", inline=False)
    
    if message.attachments:
        embed.add_field(name="Attachments", value=f"{len(message.attachments)} attachment(s)", inline=True)
    
    try:
        await log_channel.send(embed=embed)
    except Exception as e:
        print(f"Error logging deleted message: {e}")


@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    """Log edited messages."""
    if before.author.bot or before.content == after.content:
        return
    
    config = get_config(before.guild.id)
    log_channel_id = config.get('log_channel')
    
    if not log_channel_id:
        return
    
    log_channel = before.guild.get_channel(log_channel_id)
    if not log_channel:
        return
    
    embed = discord.Embed(
        title="✏️ Message Edited",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="Author", value=f"{before.author.mention} ({before.author})", inline=False)
    embed.add_field(name="Channel", value=before.channel.mention, inline=True)
    embed.add_field(name="Jump to Message", value=f"[Click here]({after.jump_url})", inline=True)
    
    before_content = before.content[:1024] if before.content else "*No content*"
    after_content = after.content[:1024] if after.content else "*No content*"
    
    embed.add_field(name="Before", value=before_content, inline=False)
    embed.add_field(name="After", value=after_content, inline=False)
    
    try:
        await log_channel.send(embed=embed)
    except Exception as e:
        print(f"Error logging edited message: {e}")


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


@bot.command(name='announce', help='Post an announcement (requires Manage Messages permission)')
@commands.has_permissions(manage_messages=True)
async def announce(ctx, channel: discord.TextChannel = None, *, message: str):
    """Post an announcement to a specified channel or current channel."""
    # Check if user has permission
    if not ctx.author.guild_permissions.manage_messages:
        await ctx.send("❌ You don't have permission to use this command. You need 'Manage Messages' permission.")
        return
    
    target_channel = channel or ctx.channel
    
    # Check if bot has permission in target channel
    if not target_channel.permissions_for(ctx.guild.me).send_messages:
        await ctx.send(f"❌ I don't have permission to send messages in {target_channel.mention}.")
        return
    
    # Create announcement embed
    embed = discord.Embed(
        title="📢 Announcement",
        description=message,
        color=discord.Color.gold(),
        timestamp=discord.utils.utcnow()
    )
    embed.set_footer(text=f"Posted by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
    
    try:
        await target_channel.send(embed=embed)
        await ctx.send(f"✅ Announcement posted in {target_channel.mention}!", delete_after=5)
    except discord.Forbidden:
        await ctx.send(f"❌ I don't have permission to send messages in {target_channel.mention}.")
    except Exception as e:
        await ctx.send(f"❌ An error occurred: {str(e)}")
        print(f"Announce error: {e}")


@bot.command(name='announcement', help='Post a detailed announcement with title (requires Manage Messages permission)')
@commands.has_permissions(manage_messages=True)
async def announcement(ctx, channel: discord.TextChannel = None, title: str = None, *, message: str):
    """Post a detailed announcement with optional title."""
    target_channel = channel or ctx.channel
    
    # Create announcement embed
    embed = discord.Embed(
        title=title or "📢 Announcement",
        description=message,
        color=discord.Color.gold(),
        timestamp=discord.utils.utcnow()
    )
    embed.set_footer(text=f"Posted by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
    
    try:
        await target_channel.send(embed=embed)
        await ctx.send(f"✅ Announcement posted in {target_channel.mention}!", delete_after=5)
    except discord.Forbidden:
        await ctx.send(f"I don't have permission to send messages in {target_channel.mention}.")


@bot.command(name='setautorole', help='Set auto-role for new members (requires Manage Roles permission)')
@commands.has_permissions(manage_roles=True)
async def set_autorole(ctx, role: discord.Role = None):
    """Set or remove auto-role for new members."""
    config = get_config(ctx.guild.id)
    
    if role is None:
        config['autorole'] = None
        await ctx.send("✅ Auto-role disabled.")
    else:
        if role >= ctx.guild.me.top_role:
            await ctx.send("❌ I cannot assign roles higher than my own role.")
            return
        config['autorole'] = role.id
        await ctx.send(f"✅ Auto-role set to {role.mention}")
    print(f"Auto-role updated for {ctx.guild.name}: {config['autorole']}")


@bot.command(name='setlogchannel', help='Set channel for logging (requires Manage Channels permission)')
@commands.has_permissions(manage_channels=True)
async def set_log_channel(ctx, channel: discord.TextChannel = None):
    """Set or remove the log channel."""
    config = get_config(ctx.guild.id)
    
    if channel is None:
        config['log_channel'] = None
        await ctx.send("✅ Log channel disabled.")
    else:
        config['log_channel'] = channel.id
        await ctx.send(f"✅ Log channel set to {channel.mention}")
    print(f"Log channel updated for {ctx.guild.name}: {config['log_channel']}")


@bot.command(name='suggest', help='Submit a suggestion')
async def suggest(ctx, *, suggestion: str):
    """Submit a suggestion to the suggestion channel."""
    config = get_config(ctx.guild.id)
    suggestion_channel_id = config.get('suggestion_channel')
    
    if not suggestion_channel_id:
        await ctx.send("❌ No suggestion channel set. Admins can set one with `!setsuggestionchannel #channel`")
        return
    
    suggestion_channel = ctx.guild.get_channel(suggestion_channel_id)
    if not suggestion_channel:
        await ctx.send("❌ Suggestion channel not found.")
        return
    
    embed = discord.Embed(
        title="💡 New Suggestion",
        description=suggestion,
        color=discord.Color.purple(),
        timestamp=discord.utils.utcnow()
    )
    embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
    embed.set_footer(text=f"Use ✅ and ❌ to vote")
    
    try:
        suggestion_msg = await suggestion_channel.send(embed=embed)
        await suggestion_msg.add_reaction("✅")
        await suggestion_msg.add_reaction("❌")
        await ctx.send(f"✅ Suggestion posted in {suggestion_channel.mention}!", delete_after=5)
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to send messages in the suggestion channel.")
    except Exception as e:
        await ctx.send(f"❌ An error occurred: {str(e)}")


@bot.command(name='setsuggestionchannel', help='Set channel for suggestions (requires Manage Channels permission)')
@commands.has_permissions(manage_channels=True)
async def set_suggestion_channel(ctx, channel: discord.TextChannel = None):
    """Set or remove the suggestion channel."""
    config = get_config(ctx.guild.id)
    
    if channel is None:
        config['suggestion_channel'] = None
        await ctx.send("✅ Suggestion channel disabled.")
    else:
        config['suggestion_channel'] = channel.id
        await ctx.send(f"✅ Suggestion channel set to {channel.mention}")
    print(f"Suggestion channel updated for {ctx.guild.name}: {config['suggestion_channel']}")


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
    # Defer immediately to prevent interaction timeout
    try:
        await interaction.response.defer(ephemeral=True)
    except discord.errors.NotFound:
        # Interaction already expired or responded to
        return
    
    # Now do validation checks
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.followup.send("❌ You don't have permission to use this command.", ephemeral=True)
        return
    
    if amount > 100:
        await interaction.followup.send("❌ You can only clear up to 100 messages at once.", ephemeral=True)
        return
    
    if amount < 1:
        await interaction.followup.send("❌ Amount must be at least 1.", ephemeral=True)
        return
    
    # Check bot permissions
    if not interaction.channel.permissions_for(interaction.guild.me).manage_messages:
        await interaction.followup.send("❌ I don't have permission to manage messages in this channel.", ephemeral=True)
        return
    
    try:
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"✅ Cleared {len(deleted)} message(s).", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("❌ I don't have permission to delete messages in this channel.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Error clearing messages: {str(e)}", ephemeral=True)
        print(f"Clear command error: {e}")


@tree.command(name="status", description="Check bot status and connection")
async def slash_status(interaction: discord.Interaction):
    """Check if the bot is working properly."""
    latency = round(bot.latency * 1000)
    embed = discord.Embed(
        title="Bot Status",
        description="Bot is online and responding!",
        color=discord.Color.green()
    )
    embed.add_field(name="Latency", value=f"{latency}ms", inline=True)
    embed.add_field(name="Guilds", value=f"{len(bot.guilds)}", inline=True)
    embed.add_field(name="Connected", value="✓ Yes", inline=True)
    
    # Check permissions
    perms = interaction.channel.permissions_for(interaction.guild.me)
    perm_status = "✓" if perms.send_messages else "✗"
    embed.add_field(name="Send Messages", value=f"{perm_status}", inline=True)
    perm_status = "✓" if perms.embed_links else "✗"
    embed.add_field(name="Embed Links", value=f"{perm_status}", inline=True)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="sync", description="Sync slash commands (Admin only)")
@app_commands.default_permissions(administrator=True)
async def slash_sync(interaction: discord.Interaction):
    """Manually sync slash commands for this server."""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ You need Administrator permission to use this command.",
            ephemeral=True
        )
        return
    
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Copy global commands to this guild and sync
        tree.copy_global_to(guild=interaction.guild)
        synced = await tree.sync(guild=interaction.guild)
        
        command_list = ', '.join([f'/{cmd.name}' for cmd in synced]) if synced else 'None'
        await interaction.followup.send(
            f"✅ Synced {len(synced)} slash command(s) to this server!\n"
            f"Commands: {command_list}\n\n"
            f"⚠️ If commands still don't appear, try restarting Discord or wait a few minutes.",
            ephemeral=True
        )
        print(f"Manually synced {len(synced)} commands for {interaction.guild.name}")
    except Exception as e:
        await interaction.followup.send(
            f"❌ Failed to sync commands: {str(e)}\n\n"
            f"Global commands are synced and should appear within 1 hour.",
            ephemeral=True
        )
        print(f"Sync error: {e}")


@tree.command(name="announce", description="Post an announcement to a channel")
@app_commands.describe(
    message="The announcement message (required)",
    channel="Channel to post the announcement (leave empty for current channel)",
    title="Optional title for the announcement",
    ping_everyone="Whether to ping @everyone (default: False)"
)
@app_commands.default_permissions(manage_messages=True)
async def slash_announce(
    interaction: discord.Interaction,
    message: str,
    channel: discord.TextChannel = None,
    title: str = None,
    ping_everyone: bool = False
):
    """Post an announcement with optional title and @everyone ping."""
    # Check user permissions
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message(
            "❌ You don't have permission to use this command. You need 'Manage Messages' permission.", 
            ephemeral=True
        )
        return
    
    target_channel = channel or interaction.channel
    
    # Check bot permissions in target channel
    if not target_channel.permissions_for(interaction.guild.me).send_messages:
        await interaction.response.send_message(
            f"❌ I don't have permission to send messages in {target_channel.mention}.",
            ephemeral=True
        )
        return
    
    # Check if trying to ping @everyone without permission
    if ping_everyone and not interaction.user.guild_permissions.mention_everyone:
        await interaction.response.send_message(
            "❌ You don't have permission to ping @everyone.",
            ephemeral=True
        )
        return
    
    # Defer response while sending announcement
    await interaction.response.defer(ephemeral=True)
    
    # Create announcement embed
    embed = discord.Embed(
        title=title or "📢 Announcement",
        description=message,
        color=discord.Color.gold(),
        timestamp=discord.utils.utcnow()
    )
    embed.set_footer(
        text=f"Posted by {interaction.user.display_name}", 
        icon_url=interaction.user.display_avatar.url
    )
    
    try:
        content = "@everyone" if ping_everyone else None
        await target_channel.send(content=content, embed=embed)
        await interaction.followup.send(
            f"✅ Announcement posted in {target_channel.mention}!",
            ephemeral=True
        )
    except discord.Forbidden:
        await interaction.followup.send(
            f"❌ I don't have permission to send messages in {target_channel.mention}.",
            ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(
            f"❌ An error occurred: {str(e)}",
            ephemeral=True
        )
        print(f"Slash announce error: {e}")


# Slash Commands for New Features
@tree.command(name="suggest", description="Submit a suggestion")
@app_commands.describe(suggestion="Your suggestion")
async def slash_suggest(interaction: discord.Interaction, suggestion: str):
    """Submit a suggestion to the suggestion channel."""
    config = get_config(interaction.guild.id)
    suggestion_channel_id = config.get('suggestion_channel')
    
    if not suggestion_channel_id:
        await interaction.response.send_message(
            "❌ No suggestion channel set. Admins can set one with `/setsuggestionchannel`",
            ephemeral=True
        )
        return
    
    suggestion_channel = interaction.guild.get_channel(suggestion_channel_id)
    if not suggestion_channel:
        await interaction.response.send_message(
            "❌ Suggestion channel not found.",
            ephemeral=True
        )
        return
    
    await interaction.response.defer(ephemeral=True)
    
    embed = discord.Embed(
        title="💡 New Suggestion",
        description=suggestion,
        color=discord.Color.purple(),
        timestamp=discord.utils.utcnow()
    )
    embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
    embed.set_footer(text=f"Use ✅ and ❌ to vote")
    
    try:
        suggestion_msg = await suggestion_channel.send(embed=embed)
        await suggestion_msg.add_reaction("✅")
        await suggestion_msg.add_reaction("❌")
        await interaction.followup.send(
            f"✅ Suggestion posted in {suggestion_channel.mention}!",
            ephemeral=True
        )
    except discord.Forbidden:
        await interaction.followup.send(
            "❌ I don't have permission to send messages in the suggestion channel.",
            ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(
            f"❌ An error occurred: {str(e)}",
            ephemeral=True
        )


@tree.command(name="setautorole", description="Set auto-role for new members (Admin only)")
@app_commands.describe(role="Role to assign automatically (leave empty to disable)")
@app_commands.default_permissions(manage_roles=True)
async def slash_set_autorole(interaction: discord.Interaction, role: discord.Role = None):
    """Set or remove auto-role for new members."""
    if not interaction.user.guild_permissions.manage_roles:
        await interaction.response.send_message(
            "❌ You need Manage Roles permission.",
            ephemeral=True
        )
        return
    
    config = get_config(interaction.guild.id)
    
    if role is None:
        config['autorole'] = None
        await interaction.response.send_message("✅ Auto-role disabled.", ephemeral=True)
    else:
        if role >= interaction.guild.me.top_role:
            await interaction.response.send_message(
                "❌ I cannot assign roles higher than my own role.",
                ephemeral=True
            )
            return
        config['autorole'] = role.id
        await interaction.response.send_message(f"✅ Auto-role set to {role.mention}", ephemeral=True)


@tree.command(name="setlogchannel", description="Set channel for logging events (Admin only)")
@app_commands.describe(channel="Channel for logs (leave empty to disable)")
@app_commands.default_permissions(manage_channels=True)
async def slash_set_log_channel(interaction: discord.Interaction, channel: discord.TextChannel = None):
    """Set or remove the log channel."""
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message(
            "❌ You need Manage Channels permission.",
            ephemeral=True
        )
        return
    
    config = get_config(interaction.guild.id)
    
    if channel is None:
        config['log_channel'] = None
        await interaction.response.send_message("✅ Log channel disabled.", ephemeral=True)
    else:
        config['log_channel'] = channel.id
        await interaction.response.send_message(f"✅ Log channel set to {channel.mention}", ephemeral=True)


@tree.command(name="setsuggestionchannel", description="Set channel for suggestions (Admin only)")
@app_commands.describe(channel="Channel for suggestions (leave empty to disable)")
@app_commands.default_permissions(manage_channels=True)
async def slash_set_suggestion_channel(interaction: discord.Interaction, channel: discord.TextChannel = None):
    """Set or remove the suggestion channel."""
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message(
            "❌ You need Manage Channels permission.",
            ephemeral=True
        )
        return
    
    config = get_config(interaction.guild.id)
    
    if channel is None:
        config['suggestion_channel'] = None
        await interaction.response.send_message("✅ Suggestion channel disabled.", ephemeral=True)
    else:
        config['suggestion_channel'] = channel.id
        await interaction.response.send_message(f"✅ Suggestion channel set to {channel.mention}", ephemeral=True)


@tree.command(name="setwelcomechannel", description="Set channel for welcome messages (Admin only)")
@app_commands.describe(channel="Channel for welcome messages (leave empty to disable)")
@app_commands.default_permissions(manage_channels=True)
async def slash_set_welcome_channel(interaction: discord.Interaction, channel: discord.TextChannel = None):
    """Set or remove the welcome channel."""
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message(
            "❌ You need Manage Channels permission.",
            ephemeral=True
        )
        return
    
    config = get_config(interaction.guild.id)
    
    if channel is None:
        config['welcome_channel_id'] = None
        await interaction.response.send_message(
            "✅ Welcome messages disabled. No welcome messages will be sent.",
            ephemeral=True
        )
    else:
        config['welcome_channel_id'] = channel.id
        await interaction.response.send_message(
            f"✅ Welcome messages will now be sent to {channel.mention}.\n"
            f"Welcome messages will only appear in this channel.",
            ephemeral=True
        )


@tree.command(name="setgoodbyechannel", description="Set channel for goodbye messages (Admin only)")
@app_commands.describe(channel="Channel for goodbye messages (leave empty to disable)")
@app_commands.default_permissions(manage_channels=True)
async def slash_set_goodbye_channel(interaction: discord.Interaction, channel: discord.TextChannel = None):
    """Set or remove the goodbye channel."""
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message(
            "❌ You need Manage Channels permission.",
            ephemeral=True
        )
        return
    
    config = get_config(interaction.guild.id)
    
    if channel is None:
        config['goodbye_channel_id'] = None
        await interaction.response.send_message("✅ Goodbye messages disabled.", ephemeral=True)
    else:
        config['goodbye_channel_id'] = channel.id
        await interaction.response.send_message(f"✅ Goodbye channel set to {channel.mention}", ephemeral=True)


# Run the bot
if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("Error: DISCORD_TOKEN not found in environment variables!")
        print("Please create a .env file with your Discord bot token.")
    else:
        bot.run(token)

