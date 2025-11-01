"""
Hansel Bot - Advanced Discord Bot
A feature-rich Discord bot similar to Dyno Bot
"""
import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import re
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict
from dotenv import load_dotenv
from database import Database
from config import APPLICATION_ID, PUBLIC_KEY

# Load environment variables
load_dotenv()

# Bot setup with all required intents
intents = discord.Intents.default()
intents.message_content = True  # Required for message content, auto-mod, logging
intents.members = True  # Required for member events, auto-roles
intents.guild_messages = True
intents.guild_reactions = True

bot = commands.Bot(command_prefix='!', intents=intents, application_id=APPLICATION_ID)
tree = bot.tree  # Slash command tree

# Initialize database
db = Database()

# Cooldown tracking for spam detection
message_history = defaultdict(list)  # {guild_id: {user_id: [timestamps]}}

# Basic profanity filter words (extend as needed)
PROFANITY_WORDS = ['badword1', 'badword2']  # Add your list here

# AFK mention tracking
afk_mentions_cache = {}


@bot.event
async def on_ready():
    """Called when the bot is ready."""
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
        synced = await tree.sync()
        print(f'✓ Synced {len(synced)} global slash command(s)')
        
        # Copy to guilds for instant availability
        for guild in bot.guilds:
            try:
                tree.copy_global_to(guild=guild)
                guild_synced = await tree.sync(guild=guild)
                print(f'✓ Synced {len(guild_synced)} command(s) to {guild.name}')
            except Exception as e:
                print(f'✗ Failed to sync to {guild.name}: {e}')
    except Exception as e:
        print(f'✗ Failed to sync slash commands: {e}')
    
    # Start background tasks
    check_mutes.start()
    check_announcements.start()
    
    # Set bot status
    await bot.change_presence(
        activity=discord.Game(name="Use /help for commands")
    )
    
    print("\n✅ Bot is ready!")


@bot.event
async def on_member_join(member: discord.Member):
    """Handle member join - welcome message and auto-role."""
    guild = member.guild
    settings = db.get_server_settings(guild.id)
    
    # Auto-role assignment
    if settings.get('autorole_id'):
        try:
            role = guild.get_role(settings['autorole_id'])
            if role and guild.me.guild_permissions.manage_roles and role < guild.me.top_role:
                await member.add_roles(role, reason="Auto-role on join")
                print(f"Assigned auto-role {role.name} to {member.name}")
        except Exception as e:
            print(f"Error assigning auto-role: {e}")
    
    # Welcome message - only send if a welcome channel is configured
    channel_id = settings.get('welcome_channel_id')
    
    # Strict check: must be a valid positive integer
    if not channel_id or channel_id == 0 or channel_id == '' or channel_id is None:
        # No welcome channel set, don't send welcome message
        return
    
    # Validate channel_id is actually a number
    try:
        channel_id = int(channel_id)
        if channel_id <= 0:
            return
    except (ValueError, TypeError):
        return
    
    channel = guild.get_channel(channel_id)
    if not channel:
        # Channel doesn't exist, don't send
        return
    
    if channel.permissions_for(guild.me).send_messages:
        embed = discord.Embed(
            title="🎉 Welcome!",
            description=f"Welcome {member.mention} to **{guild.name}**!",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Member Count", value=f"You are member #{guild.member_count}", inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="We're glad to have you here!")
        
        try:
            await channel.send(embed=embed)
        except Exception as e:
            print(f"Error sending welcome: {e}")


@bot.event
async def on_member_remove(member: discord.Member):
    """Handle member leave - goodbye message."""
    guild = member.guild
    settings = db.get_server_settings(guild.id)
    
    channel_id = settings.get('goodbye_channel_id')
    if channel_id:
        channel = guild.get_channel(channel_id)
    else:
        channel = guild.system_channel or discord.utils.get(guild.text_channels, name='general')
    
    if channel and channel.permissions_for(guild.me).send_messages:
        embed = discord.Embed(
            title="👋 Member Left",
            description=f"{member.display_name} ({member}) has left the server.",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Member Count", value=f"Now {guild.member_count} members", inline=True)
        
        try:
            await channel.send(embed=embed)
        except Exception as e:
            print(f"Error sending goodbye: {e}")


@bot.event
async def on_message(message: discord.Message):
    """Handle all messages - auto-moderation, AFK, custom commands, leveling."""
    if message.author.bot:
        return
    
    # Process custom commands (before auto-mod)
    if message.content.startswith('!'):
        parts = message.content[1:].split(' ', 1)
        if len(parts) > 0:
            cmd_name = parts[0].lower()
            custom_cmd = db.get_custom_command(message.guild.id, cmd_name)
            if custom_cmd:
                await message.channel.send(custom_cmd['command_response'])
                return  # Don't process further if custom command matched
    
    # Auto-moderation
    await check_automod(message)
    
    # AFK system - check if someone mentioned an AFK user
    if message.mentions:
        for mention in message.mentions:
            afk_data = db.is_afk(message.guild.id, mention.id)
            if afk_data:
                embed = discord.Embed(
                    description=f"{mention.mention} is AFK: {afk_data['afk_message']}",
                    color=discord.Color.orange()
                )
                await message.channel.send(embed=embed, delete_after=10)
    
    # Remove AFK if user sends a message
    afk_data = db.is_afk(message.guild.id, message.author.id)
    if afk_data:
        db.remove_afk(message.guild.id, message.author.id)
        embed = discord.Embed(
            description=f"Welcome back {message.author.mention}! Removed your AFK.",
            color=discord.Color.green()
        )
        await message.channel.send(embed=embed, delete_after=5)
    
    # Leveling system - add XP
    if message.channel.id not in [ch.id for ch in message.guild.text_channels]:  # Only text channels
        return
    
    result = db.add_xp(message.guild.id, message.author.id, 10)  # 10 XP per message
    if result['leveled_up']:
        embed = discord.Embed(
            description=f"🎉 {message.author.mention} leveled up to level **{result['level']}**!",
            color=discord.Color.gold()
        )
        await message.channel.send(embed=embed)
    
    # Process bot commands
    await bot.process_commands(message)


async def check_automod(message: discord.Message):
    """Auto-moderation checks."""
    if not message.guild:
        return
    
    config = db.get_automod_config(message.guild.id)
    
    # Check if user/role/channel is whitelisted
    if config.get('whitelisted_roles'):
        roles = [int(r) for r in config['whitelisted_roles'].split(',') if r]
        if any(role.id in roles for role in message.author.roles):
            return
    
    if config.get('whitelisted_channels'):
        channels = [int(c) for c in config['whitelisted_channels'].split(',') if c]
        if message.channel.id in channels:
            return
    
    # Spam detection
    if config.get('spam_enabled', 1):
        guild_id = message.guild.id
        user_id = message.author.id
        
        if guild_id not in message_history:
            message_history[guild_id] = defaultdict(list)
        
        now = datetime.utcnow()
        message_history[guild_id][user_id].append(now)
        
        # Clean old messages (older than 10 seconds)
        threshold = timedelta(seconds=10)
        message_history[guild_id][user_id] = [
            ts for ts in message_history[guild_id][user_id] 
            if now - ts < threshold
        ]
        
        spam_threshold = config.get('spam_threshold', 5)
        if len(message_history[guild_id][user_id]) >= spam_threshold:
            try:
                await message.delete()
                await message.channel.send(
                    f"{message.author.mention}, please slow down! (Spam detected)",
                    delete_after=5
                )
                message_history[guild_id][user_id].clear()
            except:
                pass
    
    # Profanity filter
    if config.get('profanity_enabled', 1):
        content_lower = message.content.lower()
        profanity_list = (config.get('profanity_list') or '').split(',') if config.get('profanity_list') else PROFANITY_WORDS
        
        for word in profanity_list:
            if word.strip() and word.strip() in content_lower:
                try:
                    await message.delete()
                    await message.channel.send(
                        f"{message.author.mention}, your message contained inappropriate content.",
                        delete_after=5
                    )
                    return
                except:
                    pass
    
    # Link filter
    if config.get('links_enabled', 0):
        url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
        if url_pattern.search(message.content):
            try:
                await message.delete()
                await message.channel.send(
                    f"{message.author.mention}, links are not allowed here.",
                    delete_after=5
                )
            except:
                pass
    
    # Mass ping detection
    if config.get('mass_ping_enabled', 1):
        ping_count = len(message.mentions) + len(message.role_mentions)
        ping_threshold = config.get('ping_threshold', 5)
        
        if ping_count >= ping_threshold:
            try:
                await message.delete()
                await message.channel.send(
                    f"{message.author.mention}, please don't mass ping!",
                    delete_after=5
                )
            except:
                pass


@bot.event
async def on_message_delete(message: discord.Message):
    """Log deleted messages."""
    if message.author.bot:
        return
    
    settings = db.get_server_settings(message.guild.id)
    log_channel_id = settings.get('log_channel_id')
    
    if not log_channel_id:
        return
    
    log_channel = message.guild.get_channel(log_channel_id)
    if not log_channel:
        return
    
    embed = discord.Embed(
        title="🗑️ Message Deleted",
        color=discord.Color.red(),
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Author", value=f"{message.author.mention} ({message.author})", inline=False)
    embed.add_field(name="Channel", value=message.channel.mention, inline=True)
    
    if message.content:
        embed.add_field(name="Content", value=message.content[:1024] or "*No content*", inline=False)
    
    try:
        await log_channel.send(embed=embed)
    except Exception as e:
        print(f"Error logging deleted message: {e}")


@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    """Log edited messages."""
    if before.author.bot or before.content == after.content:
        return
    
    settings = db.get_server_settings(before.guild.id)
    log_channel_id = settings.get('log_channel_id')
    
    if not log_channel_id:
        return
    
    log_channel = before.guild.get_channel(log_channel_id)
    if not log_channel:
        return
    
    embed = discord.Embed(
        title="✏️ Message Edited",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
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
async def on_member_ban(guild: discord.Guild, user: discord.User):
    """Log member bans."""
    settings = db.get_server_settings(guild.id)
    log_channel_id = settings.get('log_channel_id')
    
    if not log_channel_id:
        return
    
    log_channel = guild.get_channel(log_channel_id)
    if not log_channel:
        return
    
    embed = discord.Embed(
        title="🔨 Member Banned",
        description=f"{user.mention} ({user}) has been banned.",
        color=discord.Color.red(),
        timestamp=datetime.utcnow()
    )
    
    try:
        await log_channel.send(embed=embed)
    except Exception as e:
        print(f"Error logging ban: {e}")


@bot.event
async def on_member_remove(member: discord.Member):
    """Log member kicks (if they were kicked)."""
    # This also handles leave messages, but we check if it was a kick
    settings = db.get_server_settings(member.guild.id)
    log_channel_id = settings.get('log_channel_id')
    
    if log_channel_id:
        log_channel = member.guild.get_channel(log_channel_id)
        if log_channel:
            # Try to get audit log to check if it was a kick
            try:
                async for entry in member.guild.audit_logs(action=discord.AuditLogAction.kick, limit=1):
                    if entry.target == member:
                        embed = discord.Embed(
                            title="👢 Member Kicked",
                            description=f"{member.mention} ({member}) has been kicked.",
                            color=discord.Color.orange(),
                            timestamp=datetime.utcnow()
                        )
                        if entry.reason:
                            embed.add_field(name="Reason", value=entry.reason, inline=False)
                        await log_channel.send(embed=embed)
                        return
            except:
                pass


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    """Handle reaction roles."""
    if payload.member.bot:
        return
    
    reaction_roles = db.get_reaction_roles(payload.guild_id, payload.message_id)
    
    for rr in reaction_roles:
        emoji_str = str(payload.emoji)
        if emoji_str == rr['emoji'] or payload.emoji.name == rr['emoji']:
            guild = bot.get_guild(payload.guild_id)
            role = guild.get_role(rr['role_id'])
            member = payload.member
            
            if role and member:
                try:
                    await member.add_roles(role, reason="Reaction role")
                    print(f"Assigned role {role.name} to {member.name} via reaction")
                except Exception as e:
                    print(f"Error assigning reaction role: {e}")


@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    """Handle reaction role removal."""
    reaction_roles = db.get_reaction_roles(payload.guild_id, payload.message_id)
    
    for rr in reaction_roles:
        emoji_str = str(payload.emoji)
        if emoji_str == rr['emoji'] or payload.emoji.name == rr['emoji']:
            guild = bot.get_guild(payload.guild_id)
            role = guild.get_role(rr['role_id'])
            member = guild.get_member(payload.user_id)
            
            if role and member:
                try:
                    await member.remove_roles(role, reason="Reaction role removed")
                except Exception as e:
                    print(f"Error removing reaction role: {e}")


@tasks.loop(minutes=1)
async def check_mutes():
    """Check for expired mutes."""
    for guild in bot.guilds:
        muted_users = db.get_muted_users(guild.id)
        for mute_data in muted_users:
            if mute_data.get('unmute_time'):
                unmute_time = datetime.fromisoformat(mute_data['unmute_time'])
                if datetime.utcnow() >= unmute_time:
                    user = guild.get_member(mute_data['user_id'])
                    if user:
                        mute_role = guild.get_role(mute_data['mute_role_id'])
                        if mute_role:
                            try:
                                await user.remove_roles(mute_role, reason="Mute expired")
                                db.remove_mute(guild.id, mute_data['user_id'])
                                print(f"Unmuted {user.name} (expired)")
                            except Exception as e:
                                print(f"Error unmuting: {e}")


@tasks.loop(minutes=1)
async def check_announcements():
    """Check and send scheduled announcements."""
    announcements = db.get_due_announcements()
    
    for ann in announcements:
        guild = bot.get_guild(ann['guild_id'])
        if not guild:
            continue
        
        channel = guild.get_channel(ann['channel_id'])
        if not channel:
            continue
        
        try:
            embed = discord.Embed(
                title="📢 Automated Announcement",
                description=ann['message'],
                color=discord.Color.gold(),
                timestamp=datetime.utcnow()
            )
            await channel.send(embed=embed)
            db.update_announcement_next_run(ann['id'])
        except Exception as e:
            print(f"Error sending announcement: {e}")


# MODERATION COMMANDS

@tree.command(name="ban", description="Ban a member from the server")
@app_commands.describe(member="Member to ban", reason="Reason for ban")
@app_commands.default_permissions(ban_members=True)
async def slash_ban(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    """Ban a member."""
    if not interaction.user.guild_permissions.ban_members:
        await interaction.response.send_message("❌ You need Ban Members permission.", ephemeral=True)
        return
    
    if member == interaction.user:
        await interaction.response.send_message("❌ You cannot ban yourself!", ephemeral=True)
        return
    
    if member.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
        await interaction.response.send_message("❌ You cannot ban someone with equal or higher roles!", ephemeral=True)
        return
    
    try:
        await member.ban(reason=reason or f"Banned by {interaction.user}")
        embed = discord.Embed(
            title="🔨 Member Banned",
            description=f"{member.mention} has been banned.",
            color=discord.Color.red()
        )
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to ban this member.", ephemeral=True)


@tree.command(name="kick", description="Kick a member from the server")
@app_commands.describe(member="Member to kick", reason="Reason for kick")
@app_commands.default_permissions(kick_members=True)
async def slash_kick(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    """Kick a member."""
    if not interaction.user.guild_permissions.kick_members:
        await interaction.response.send_message("❌ You need Kick Members permission.", ephemeral=True)
        return
    
    if member == interaction.user:
        await interaction.response.send_message("❌ You cannot kick yourself!", ephemeral=True)
        return
    
    try:
        await member.kick(reason=reason or f"Kicked by {interaction.user}")
        embed = discord.Embed(
            title="👢 Member Kicked",
            description=f"{member.mention} has been kicked.",
            color=discord.Color.orange()
        )
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to kick this member.", ephemeral=True)


@tree.command(name="mute", description="Mute a member (timeout or role)")
@app_commands.describe(
    member="Member to mute",
    duration="Duration in minutes (0 for permanent)",
    reason="Reason for mute"
)
@app_commands.default_permissions(moderate_members=True)
async def slash_mute(interaction: discord.Interaction, member: discord.Member, duration: int = 0, reason: str = None):
    """Mute a member."""
    if not interaction.user.guild_permissions.moderate_members:
        await interaction.response.send_message("❌ You need Moderate Members permission.", ephemeral=True)
        return
    
    await interaction.response.defer()
    
    # Try timeout first (Discord's built-in mute)
    if duration > 0:
        timeout_until = datetime.utcnow() + timedelta(minutes=duration)
        try:
            await member.timeout(timeout_until, reason=reason)
            embed = discord.Embed(
                title="🔇 Member Muted",
                description=f"{member.mention} has been muted for {duration} minutes.",
                color=discord.Color.orange()
            )
            if reason:
                embed.add_field(name="Reason", value=reason, inline=False)
            await interaction.followup.send(embed=embed)
            return
        except:
            pass  # Fall back to role mute
    
    # Fall back to role-based mute
    mute_role = discord.utils.get(interaction.guild.roles, name="Muted")
    if not mute_role:
        # Create mute role
        mute_role = await interaction.guild.create_role(
            name="Muted",
            reason="Mute role creation"
        )
        # Deny permissions for mute role
        for channel in interaction.guild.channels:
            try:
                await channel.set_permissions(mute_role, send_messages=False, speak=False)
            except:
                pass
    
    try:
        await member.add_roles(mute_role, reason=reason or f"Muted by {interaction.user}")
        unmute_time = None
        if duration > 0:
            unmute_time = (datetime.utcnow() + timedelta(minutes=duration)).isoformat()
        
        db.add_mute(interaction.guild.id, member.id, mute_role.id, unmute_time)
        
        embed = discord.Embed(
            title="🔇 Member Muted",
            description=f"{member.mention} has been muted.",
            color=discord.Color.orange()
        )
        if duration > 0:
            embed.add_field(name="Duration", value=f"{duration} minutes", inline=True)
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ Error muting member: {str(e)}")


@tree.command(name="unmute", description="Unmute a member")
@app_commands.describe(member="Member to unmute")
@app_commands.default_permissions(moderate_members=True)
async def slash_unmute(interaction: discord.Interaction, member: discord.Member):
    """Unmute a member."""
    if not interaction.user.guild_permissions.moderate_members:
        await interaction.response.send_message("❌ You need Moderate Members permission.", ephemeral=True)
        return
    
    await interaction.response.defer()
    
    # Remove timeout
    try:
        await member.timeout(None)
    except:
        pass
    
    # Remove mute role
    mute_role = discord.utils.get(interaction.guild.roles, name="Muted")
    if mute_role and mute_role in member.roles:
        try:
            await member.remove_roles(mute_role, reason=f"Unmuted by {interaction.user}")
        except:
            pass
    
    db.remove_mute(interaction.guild.id, member.id)
    
    embed = discord.Embed(
        title="🔊 Member Unmuted",
        description=f"{member.mention} has been unmuted.",
        color=discord.Color.green()
    )
    await interaction.followup.send(embed=embed)


@tree.command(name="warn", description="Warn a member")
@app_commands.describe(member="Member to warn", reason="Reason for warning")
@app_commands.default_permissions(moderate_members=True)
async def slash_warn(interaction: discord.Interaction, member: discord.Member, reason: str):
    """Warn a member."""
    if not interaction.user.guild_permissions.moderate_members:
        await interaction.response.send_message("❌ You need Moderate Members permission.", ephemeral=True)
        return
    
    warning_id = db.add_warning(interaction.guild.id, member.id, interaction.user.id, reason)
    warnings = db.get_warnings(interaction.guild.id, member.id)
    
    embed = discord.Embed(
        title="⚠️ Member Warned",
        description=f"{member.mention} has been warned.",
        color=discord.Color.orange()
    )
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="Total Warnings", value=f"{len(warnings)}", inline=True)
    embed.set_footer(text=f"Warning ID: {warning_id}")
    
    await interaction.response.send_message(embed=embed)
    
    # DM the member
    try:
        dm_embed = discord.Embed(
            title="⚠️ You have been warned",
            description=f"You received a warning in {interaction.guild.name}",
            color=discord.Color.orange()
        )
        dm_embed.add_field(name="Reason", value=reason, inline=False)
        await member.send(embed=dm_embed)
    except:
        pass  # User has DMs disabled


@tree.command(name="warnings", description="View warnings for a member")
@app_commands.describe(member="Member to check warnings for")
@app_commands.default_permissions(moderate_members=True)
async def slash_warnings(interaction: discord.Interaction, member: discord.Member):
    """View member warnings."""
    warnings = db.get_warnings(interaction.guild.id, member.id)
    
    if not warnings:
        await interaction.response.send_message(f"✅ {member.mention} has no warnings.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title=f"⚠️ Warnings for {member.display_name}",
        description=f"Total: {len(warnings)}",
        color=discord.Color.orange()
    )
    
    for i, warning in enumerate(warnings[:10], 1):  # Show last 10
        moderator = interaction.guild.get_member(warning['moderator_id'])
        mod_name = moderator.display_name if moderator else "Unknown"
        embed.add_field(
            name=f"Warning #{warning['id']}",
            value=f"**Reason:** {warning['reason']}\n**Moderator:** {mod_name}\n**Date:** {warning['timestamp'][:10]}",
            inline=False
        )
    
    await interaction.response.send_message(embed=embed)


@tree.command(name="clearwarnings", description="Clear all warnings for a member")
@app_commands.describe(member="Member to clear warnings for")
@app_commands.default_permissions(administrator=True)
async def slash_clear_warnings(interaction: discord.Interaction, member: discord.Member):
    """Clear all warnings."""
    count = db.clear_warnings(interaction.guild.id, member.id)
    embed = discord.Embed(
        description=f"✅ Cleared {count} warning(s) for {member.mention}.",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)


@tree.command(name="purge", description="Delete multiple messages")
@app_commands.describe(amount="Number of messages to delete (1-100)")
@app_commands.default_permissions(manage_messages=True)
async def slash_purge(interaction: discord.Interaction, amount: int = 10):
    """Purge messages."""
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("❌ You need Manage Messages permission.", ephemeral=True)
        return
    
    if amount < 1 or amount > 100:
        await interaction.response.send_message("❌ Amount must be between 1 and 100.", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    try:
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"✅ Deleted {len(deleted)} message(s).", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)


# CUSTOM COMMANDS

@tree.command(name="addcommand", description="Add a custom command (Admin only)")
@app_commands.describe(command="Command name (without prefix)", response="Response text")
@app_commands.default_permissions(administrator=True)
async def slash_add_command(interaction: discord.Interaction, command: str, response: str):
    """Add a custom command."""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need Administrator permission.", ephemeral=True)
        return
    
    success = db.add_custom_command(interaction.guild.id, command, response)
    if success:
        await interaction.response.send_message(
            f"✅ Custom command `{command}` added! Use `!{command}` to trigger it.",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"❌ Command `{command}` already exists! Use `/deletecommand` to remove it first.",
            ephemeral=True
        )


@tree.command(name="deletecommand", description="Delete a custom command (Admin only)")
@app_commands.describe(command="Command name to delete")
@app_commands.default_permissions(administrator=True)
async def slash_delete_command(interaction: discord.Interaction, command: str):
    """Delete a custom command."""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need Administrator permission.", ephemeral=True)
        return
    
    success = db.delete_custom_command(interaction.guild.id, command)
    if success:
        await interaction.response.send_message(f"✅ Command `{command}` deleted!", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ Command `{command}` not found.", ephemeral=True)


@tree.command(name="listcommands", description="List all custom commands")
async def slash_list_commands(interaction: discord.Interaction):
    """List all custom commands."""
    commands = db.get_all_custom_commands(interaction.guild.id)
    
    if not commands:
        await interaction.response.send_message("No custom commands set up yet.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="Custom Commands",
        description=f"Total: {len(commands)}",
        color=discord.Color.blue()
    )
    
    cmd_list = "\n".join([f"`!{cmd['command_name']}`" for cmd in commands[:20]])
    embed.add_field(name="Commands", value=cmd_list or "None", inline=False)
    
    await interaction.response.send_message(embed=embed)


# REACTION ROLES

@tree.command(name="addreactionrole", description="Add a reaction role to a message (Admin only)")
@app_commands.describe(
    message_id="ID of the message to add reaction to",
    emoji="Emoji to use",
    role="Role to assign"
)
@app_commands.default_permissions(administrator=True)
async def slash_add_reaction_role(
    interaction: discord.Interaction,
    message_id: str,
    emoji: str,
    role: discord.Role
):
    """Add a reaction role."""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need Administrator permission.", ephemeral=True)
        return
    
    try:
        msg_id = int(message_id)
        message = await interaction.channel.fetch_message(msg_id)
        
        # Add reaction
        emoji_obj = emoji if emoji.startswith('<') else emoji
        await message.add_reaction(emoji_obj)
        
        # Store in database
        db.add_reaction_role(
            interaction.guild.id,
            msg_id,
            interaction.channel.id,
            emoji,
            role.id
        )
        
        await interaction.response.send_message(
            f"✅ Reaction role added! React with {emoji} on that message to get {role.mention}",
            ephemeral=True
        )
    except discord.NotFound:
        await interaction.response.send_message("❌ Message not found. Make sure the message ID is correct.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)


# AFK SYSTEM

@tree.command(name="afk", description="Set your AFK status")
@app_commands.describe(message="AFK message (optional)")
async def slash_afk(interaction: discord.Interaction, message: str = "AFK"):
    """Set AFK status."""
    db.set_afk(interaction.guild.id, interaction.user.id, message)
    embed = discord.Embed(
        description=f"✅ You are now AFK: {message}",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed, delete_after=5)


# LEVELING SYSTEM

@tree.command(name="level", description="Check your or someone's level")
@app_commands.describe(member="Member to check (leave empty for yourself)")
async def slash_level(interaction: discord.Interaction, member: discord.Member = None):
    """Check user level."""
    target = member or interaction.user
    data = db.get_user_level(interaction.guild.id, target.id)
    
    # Calculate XP needed for next level
    current_level_xp = (data['level'] - 1) ** 2 * 100
    next_level_xp = data['level'] ** 2 * 100
    xp_progress = data['xp'] - current_level_xp
    xp_needed = next_level_xp - current_level_xp
    
    embed = discord.Embed(
        title=f"Level Info - {target.display_name}",
        color=discord.Color.gold()
    )
    embed.add_field(name="Level", value=f"{data['level']}", inline=True)
    embed.add_field(name="XP", value=f"{data['xp']}", inline=True)
    embed.add_field(name="Messages", value=f"{data['total_messages']}", inline=True)
    embed.add_field(
        name="Progress to Next Level",
        value=f"{xp_progress}/{xp_needed} XP",
        inline=False
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    
    await interaction.response.send_message(embed=embed)


@tree.command(name="leaderboard", description="View server level leaderboard")
async def slash_leaderboard(interaction: discord.Interaction):
    """Show level leaderboard."""
    leaderboard = db.get_leaderboard(interaction.guild.id, limit=10)
    
    if not leaderboard:
        await interaction.response.send_message("No leveling data yet!", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="🏆 Server Leaderboard",
        color=discord.Color.gold()
    )
    
    leaderboard_text = ""
    for i, entry in enumerate(leaderboard, 1):
        user = interaction.guild.get_member(entry['user_id'])
        name = user.display_name if user else "Unknown User"
        leaderboard_text += f"**{i}.** {name} - Level {entry['level']} ({entry['xp']} XP)\n"
    
    embed.description = leaderboard_text
    await interaction.response.send_message(embed=embed)


# CONFIGURATION COMMANDS

@tree.command(name="setautorole", description="Set auto-role for new members (Admin only)")
@app_commands.describe(role="Role to assign automatically (leave empty to disable)")
@app_commands.default_permissions(manage_roles=True)
async def slash_set_autorole(interaction: discord.Interaction, role: discord.Role = None):
    """Set auto-role."""
    if not interaction.user.guild_permissions.manage_roles:
        await interaction.response.send_message("❌ You need Manage Roles permission.", ephemeral=True)
        return
    
    if role and role >= interaction.guild.me.top_role:
        await interaction.response.send_message(
            "❌ I cannot assign roles higher than my own role.",
            ephemeral=True
        )
        return
    
    db.update_server_setting(interaction.guild.id, 'autorole_id', role.id if role else None)
    
    if role:
        await interaction.response.send_message(f"✅ Auto-role set to {role.mention}", ephemeral=True)
    else:
        await interaction.response.send_message("✅ Auto-role disabled", ephemeral=True)


@tree.command(name="setlogchannel", description="Set channel for logging (Admin only)")
@app_commands.describe(channel="Channel for logs (leave empty to disable)")
@app_commands.default_permissions(manage_channels=True)
async def slash_set_log_channel(interaction: discord.Interaction, channel: discord.TextChannel = None):
    """Set log channel."""
    db.update_server_setting(interaction.guild.id, 'log_channel_id', channel.id if channel else None)
    
    if channel:
        await interaction.response.send_message(f"✅ Log channel set to {channel.mention}", ephemeral=True)
    else:
        await interaction.response.send_message("✅ Log channel disabled", ephemeral=True)


@tree.command(name="setwelcomechannel", description="Set channel for welcome messages (Admin only)")
@app_commands.describe(channel="Channel for welcome messages (leave empty to disable)")
@app_commands.default_permissions(manage_channels=True)
async def slash_set_welcome_channel(interaction: discord.Interaction, channel: discord.TextChannel = None):
    """Set welcome channel. Leave empty to disable welcome messages."""
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("❌ You need Manage Channels permission.", ephemeral=True)
        return
    
    if channel:
        db.update_server_setting(interaction.guild.id, 'welcome_channel_id', channel.id)
        await interaction.response.send_message(
            f"✅ Welcome messages will now be sent to {channel.mention}.\n"
            f"Welcome messages will only appear in the configured channel.",
            ephemeral=True
        )
    else:
        # Explicitly set to NULL/None - use direct SQL for guaranteed clear
        cursor = db.conn.cursor()
        cursor.execute("UPDATE server_settings SET welcome_channel_id = NULL WHERE guild_id = ?", (interaction.guild.id,))
        db.conn.commit()
        
        # Double-check it's cleared
        cursor.execute("SELECT welcome_channel_id FROM server_settings WHERE guild_id = ?", (interaction.guild.id,))
        result = cursor.fetchone()
        cleared_value = result[0] if result else None
        
        if cleared_value is None or cleared_value == 0:
            await interaction.response.send_message(
                "✅ Welcome messages **COMPLETELY DISABLED**.\n"
                "No welcome messages will be sent when members join.\n\n"
                "💡 **Important:** Make sure only **ONE bot is running**:\n"
                "- Run `python bot_advanced.py` (recommended)\n"
                "- OR run `python bot.py` (basic version)\n"
                "- **NOT both at the same time!**",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"⚠️ **Warning:** Attempted to disable, but database still shows: {cleared_value}\n"
                "Please restart the bot and try again.",
                ephemeral=True
            )


@tree.command(name="setgoodbyechannel", description="Set channel for goodbye messages (Admin only)")
@app_commands.describe(channel="Channel for goodbyes (leave empty to disable)")
@app_commands.default_permissions(manage_channels=True)
async def slash_set_goodbye_channel(interaction: discord.Interaction, channel: discord.TextChannel = None):
    """Set goodbye channel."""
    db.update_server_setting(interaction.guild.id, 'goodbye_channel_id', channel.id if channel else None)
    
    if channel:
        await interaction.response.send_message(f"✅ Goodbye channel set to {channel.mention}", ephemeral=True)
    else:
        await interaction.response.send_message("✅ Goodbye channel disabled", ephemeral=True)


# AUTO-MOD CONFIGURATION

@tree.command(name="automod", description="Configure auto-moderation (Admin only)")
@app_commands.describe(
    spam="Enable/disable spam detection",
    profanity="Enable/disable profanity filter",
    links="Enable/disable link filter",
    mass_ping="Enable/disable mass ping detection"
)
@app_commands.default_permissions(administrator=True)
async def slash_automod(
    interaction: discord.Interaction,
    spam: bool = None,
    profanity: bool = None,
    links: bool = None,
    mass_ping: bool = None
):
    """Configure auto-moderation."""
    config = db.get_automod_config(interaction.guild.id)
    changes = []
    
    if spam is not None:
        db.update_automod_setting(interaction.guild.id, 'spam_enabled', int(spam))
        changes.append(f"Spam detection: {'✅ Enabled' if spam else '❌ Disabled'}")
    
    if profanity is not None:
        db.update_automod_setting(interaction.guild.id, 'profanity_enabled', int(profanity))
        changes.append(f"Profanity filter: {'✅ Enabled' if profanity else '❌ Disabled'}")
    
    if links is not None:
        db.update_automod_setting(interaction.guild.id, 'links_enabled', int(links))
        changes.append(f"Link filter: {'✅ Enabled' if links else '❌ Disabled'}")
    
    if mass_ping is not None:
        db.update_automod_setting(interaction.guild.id, 'mass_ping_enabled', int(mass_ping))
        changes.append(f"Mass ping detection: {'✅ Enabled' if mass_ping else '❌ Disabled'}")
    
    if changes:
        embed = discord.Embed(
            title="Auto-Mod Configuration Updated",
            description="\n".join(changes),
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        # Show current config
        embed = discord.Embed(
            title="Auto-Mod Configuration",
            color=discord.Color.blue()
        )
        embed.add_field(name="Spam Detection", value="✅ Enabled" if config.get('spam_enabled') else "❌ Disabled", inline=True)
        embed.add_field(name="Profanity Filter", value="✅ Enabled" if config.get('profanity_enabled') else "❌ Disabled", inline=True)
        embed.add_field(name="Link Filter", value="✅ Enabled" if config.get('links_enabled') else "❌ Disabled", inline=True)
        embed.add_field(name="Mass Ping Detection", value="✅ Enabled" if config.get('mass_ping_enabled') else "❌ Disabled", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)


# SCHEDULED ANNOUNCEMENTS

@tree.command(name="scheduleannouncement", description="Schedule a repeating announcement (Admin only)")
@app_commands.describe(
    channel="Channel for announcement",
    message="Announcement message",
    interval="Interval in minutes"
)
@app_commands.default_permissions(administrator=True)
async def slash_schedule_announcement(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    message: str,
    interval: int
):
    """Schedule a repeating announcement."""
    if interval < 1:
        await interaction.response.send_message("❌ Interval must be at least 1 minute.", ephemeral=True)
        return
    
    announcement_id = db.add_scheduled_announcement(
        interaction.guild.id,
        channel.id,
        message,
        interval
    )
    
    embed = discord.Embed(
        title="✅ Announcement Scheduled",
        description=f"Announcement will be sent every {interval} minutes in {channel.mention}",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


# UTILITY COMMANDS

@tree.command(name="ping", description="Check bot latency")
async def slash_ping(interaction: discord.Interaction):
    """Check bot latency."""
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"Pong! Latency: {latency}ms")


@tree.command(name="serverinfo", description="Display server information")
async def slash_server_info(interaction: discord.Interaction):
    """Show server info."""
    guild = interaction.guild
    embed = discord.Embed(
        title=f"Server: {guild.name}",
        description=f"Members: {guild.member_count}",
        color=discord.Color.blue()
    )
    embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
    embed.add_field(name="Created", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="Channels", value=f"{len(guild.text_channels)} text, {len(guild.voice_channels)} voice", inline=True)
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    await interaction.response.send_message(embed=embed)


@tree.command(name="botconfig", description="View current bot configuration (Admin only)")
@app_commands.default_permissions(administrator=True)
async def slash_bot_config(interaction: discord.Interaction):
    """View current bot configuration."""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need Administrator permission.", ephemeral=True)
        return
    
    settings = db.get_server_settings(interaction.guild.id)
    
    embed = discord.Embed(
        title="Bot Configuration",
        description="Current bot settings for this server",
        color=discord.Color.blue()
    )
    
    # Welcome channel
    welcome_id = settings.get('welcome_channel_id')
    if welcome_id and welcome_id != 0:
        welcome_ch = interaction.guild.get_channel(welcome_id)
        welcome_text = welcome_ch.mention if welcome_ch else f"Channel ID: {welcome_id} (not found)"
    else:
        welcome_text = "❌ **DISABLED** - No welcome messages"
    embed.add_field(name="Welcome Channel", value=welcome_text, inline=False)
    
    # Goodbye channel
    goodbye_id = settings.get('goodbye_channel_id')
    if goodbye_id and goodbye_id != 0:
        goodbye_ch = interaction.guild.get_channel(goodbye_id)
        goodbye_text = goodbye_ch.mention if goodbye_ch else f"Channel ID: {goodbye_id} (not found)"
    else:
        goodbye_text = "❌ **DISABLED** - No goodbye messages"
    embed.add_field(name="Goodbye Channel", value=goodbye_text, inline=False)
    
    # Log channel
    log_id = settings.get('log_channel_id')
    if log_id and log_id != 0:
        log_ch = interaction.guild.get_channel(log_id)
        log_text = log_ch.mention if log_ch else f"Channel ID: {log_id} (not found)"
    else:
        log_text = "❌ **DISABLED** - No logging"
    embed.add_field(name="Log Channel", value=log_text, inline=False)
    
    # Auto-role
    autorole_id = settings.get('autorole_id')
    if autorole_id and autorole_id != 0:
        role = interaction.guild.get_role(autorole_id)
        autorole_text = role.mention if role else f"Role ID: {autorole_id} (not found)"
    else:
        autorole_text = "❌ **DISABLED** - No auto-role"
    embed.add_field(name="Auto-Role", value=autorole_text, inline=False)
    
    embed.set_footer(text="Use /setwelcomechannel (empty) to disable welcome messages")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="disablewelcome", description="Force disable welcome messages (Admin only)")
@app_commands.default_permissions(administrator=True)
async def slash_disable_welcome(interaction: discord.Interaction):
    """Force disable welcome messages completely."""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need Administrator permission.", ephemeral=True)
        return
    
    # Force clear using direct SQL
    cursor = db.conn.cursor()
    cursor.execute("UPDATE server_settings SET welcome_channel_id = NULL WHERE guild_id = ?", (interaction.guild.id,))
    db.conn.commit()
    
    # Verify
    cursor.execute("SELECT welcome_channel_id FROM server_settings WHERE guild_id = ?", (interaction.guild.id,))
    result = cursor.fetchone()
    value = result[0] if result else None
    
    if value is None or value == 0:
        await interaction.response.send_message(
            "✅ **Welcome messages are now COMPLETELY DISABLED.**\n\n"
            "No welcome messages will be sent when members join your server.\n\n"
            "⚠️ **Check:** Make sure you're only running **ONE bot instance**:\n"
            "- `bot_advanced.py` (recommended) OR\n"
            "- `bot.py` (basic)\n"
            "- **NOT both at the same time!**",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"❌ Error: Could not disable. Value is still: {value}\n"
            "Please try restarting the bot and running this command again.",
            ephemeral=True
        )


# Run the bot
if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("Error: DISCORD_TOKEN not found in environment variables!")
        print("Please create a .env file with your Discord bot token.")
    else:
        try:
            bot.run(token)
        finally:
            db.close()

