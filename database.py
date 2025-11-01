"""
Database module for storing server configurations and data.
Uses SQLite for simplicity - can be upgraded to PostgreSQL/MySQL later.
"""
import sqlite3
import os
from typing import Optional, Dict, List, Tuple

DB_PATH = "bot_data.db"


class Database:
    def __init__(self):
        self.conn = None
        self.init_database()
    
    def init_database(self):
        """Initialize database and create tables if they don't exist."""
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        cursor = self.conn.cursor()
        
        # Server settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS server_settings (
                guild_id INTEGER PRIMARY KEY,
                autorole_id INTEGER,
                log_channel_id INTEGER,
                suggestion_channel_id INTEGER,
                welcome_channel_id INTEGER,
                goodbye_channel_id INTEGER,
                automod_enabled INTEGER DEFAULT 1,
                spam_threshold INTEGER DEFAULT 5,
                profanity_filter INTEGER DEFAULT 1,
                link_filter INTEGER DEFAULT 0,
                mass_ping_threshold INTEGER DEFAULT 5
            )
        """)
        
        # Auto-moderation config
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS automod_config (
                guild_id INTEGER PRIMARY KEY,
                spam_enabled INTEGER DEFAULT 1,
                profanity_enabled INTEGER DEFAULT 1,
                links_enabled INTEGER DEFAULT 0,
                mass_ping_enabled INTEGER DEFAULT 1,
                spam_threshold INTEGER DEFAULT 5,
                ping_threshold INTEGER DEFAULT 5,
                profanity_list TEXT,
                whitelisted_roles TEXT,
                whitelisted_channels TEXT
            )
        """)
        
        # Custom commands table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS custom_commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                command_name TEXT NOT NULL,
                command_response TEXT NOT NULL,
                UNIQUE(guild_id, command_name)
            )
        """)
        
        # Warnings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                moderator_id INTEGER NOT NULL,
                reason TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        
        # Muted users table (for temporary mutes)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS muted_users (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                mute_role_id INTEGER,
                unmute_time TEXT,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
        
        # Reaction roles table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reaction_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                emoji TEXT NOT NULL,
                role_id INTEGER NOT NULL
            )
        """)
        
        # Leveling system
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_levels (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                total_messages INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
        
        # AFK users
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS afk_users (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                afk_message TEXT,
                afk_since TEXT NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
        
        # Scheduled announcements
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_announcements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                interval_minutes INTEGER,
                next_run TEXT NOT NULL,
                enabled INTEGER DEFAULT 1
            )
        """)
        
        # Message logging
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS message_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                content TEXT,
                action TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        
        self.conn.commit()
        print("✅ Database initialized successfully")
    
    # Server Settings Methods
    def get_server_settings(self, guild_id: int) -> Dict:
        """Get server settings or create default."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM server_settings WHERE guild_id = ?", (guild_id,))
        row = cursor.fetchone()
        
        if row:
            settings = dict(row)
            # Ensure None values are properly None (not empty strings or 0)
            for key in ['welcome_channel_id', 'goodbye_channel_id', 'log_channel_id', 'autorole_id', 'suggestion_channel_id']:
                if key in settings and (settings[key] == 0 or settings[key] == ''):
                    settings[key] = None
            return settings
        else:
            # Create default settings
            cursor.execute("""
                INSERT INTO server_settings (guild_id) VALUES (?)
            """, (guild_id,))
            self.conn.commit()
            return self.get_server_settings(guild_id)
    
    def update_server_setting(self, guild_id: int, setting: str, value):
        """Update a server setting."""
        cursor = self.conn.cursor()
        # First ensure row exists
        self.get_server_settings(guild_id)
        # Use NULL explicitly for None values
        if value is None:
            cursor.execute(f"UPDATE server_settings SET {setting} = NULL WHERE guild_id = ?", (guild_id,))
        else:
            cursor.execute(f"UPDATE server_settings SET {setting} = ? WHERE guild_id = ?", (value, guild_id))
        self.conn.commit()
        
        # Verify the update
        cursor.execute(f"SELECT {setting} FROM server_settings WHERE guild_id = ?", (guild_id,))
        result = cursor.fetchone()
        if result:
            print(f"[DB DEBUG] Updated {setting} for guild {guild_id} to: {result[0]}")
    
    # Custom Commands Methods
    def add_custom_command(self, guild_id: int, command_name: str, response: str):
        """Add a custom command."""
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO custom_commands (guild_id, command_name, command_response)
                VALUES (?, ?, ?)
            """, (guild_id, command_name.lower(), response))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # Command already exists
    
    def get_custom_command(self, guild_id: int, command_name: str) -> Optional[Dict]:
        """Get a custom command."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM custom_commands 
            WHERE guild_id = ? AND command_name = ?
        """, (guild_id, command_name.lower()))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_all_custom_commands(self, guild_id: int) -> List[Dict]:
        """Get all custom commands for a guild."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM custom_commands WHERE guild_id = ?
        """, (guild_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def delete_custom_command(self, guild_id: int, command_name: str):
        """Delete a custom command."""
        cursor = self.conn.cursor()
        cursor.execute("""
            DELETE FROM custom_commands 
            WHERE guild_id = ? AND command_name = ?
        """, (guild_id, command_name.lower()))
        self.conn.commit()
        return cursor.rowcount > 0
    
    # Warnings Methods
    def add_warning(self, guild_id: int, user_id: int, moderator_id: int, reason: str):
        """Add a warning to a user."""
        cursor = self.conn.cursor()
        from datetime import datetime
        cursor.execute("""
            INSERT INTO warnings (guild_id, user_id, moderator_id, reason, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (guild_id, user_id, moderator_id, reason, datetime.utcnow().isoformat()))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_warnings(self, guild_id: int, user_id: int) -> List[Dict]:
        """Get all warnings for a user."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM warnings 
            WHERE guild_id = ? AND user_id = ?
            ORDER BY timestamp DESC
        """, (guild_id, user_id))
        return [dict(row) for row in cursor.fetchall()]
    
    def clear_warnings(self, guild_id: int, user_id: int):
        """Clear all warnings for a user."""
        cursor = self.conn.cursor()
        cursor.execute("""
            DELETE FROM warnings WHERE guild_id = ? AND user_id = ?
        """, (guild_id, user_id))
        self.conn.commit()
        return cursor.rowcount
    
    # Mute Methods
    def add_mute(self, guild_id: int, user_id: int, mute_role_id: int, unmute_time: str = None):
        """Add a muted user."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO muted_users (guild_id, user_id, mute_role_id, unmute_time)
            VALUES (?, ?, ?, ?)
        """, (guild_id, user_id, mute_role_id, unmute_time))
        self.conn.commit()
    
    def remove_mute(self, guild_id: int, user_id: int):
        """Remove a muted user."""
        cursor = self.conn.cursor()
        cursor.execute("""
            DELETE FROM muted_users WHERE guild_id = ? AND user_id = ?
        """, (guild_id, user_id))
        self.conn.commit()
    
    def get_muted_users(self, guild_id: int) -> List[Dict]:
        """Get all muted users."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM muted_users WHERE guild_id = ?
        """, (guild_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    # Reaction Roles Methods
    def add_reaction_role(self, guild_id: int, message_id: int, channel_id: int, emoji: str, role_id: int):
        """Add a reaction role."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO reaction_roles (guild_id, message_id, channel_id, emoji, role_id)
            VALUES (?, ?, ?, ?, ?)
        """, (guild_id, message_id, channel_id, emoji, role_id))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_reaction_roles(self, guild_id: int, message_id: int = None) -> List[Dict]:
        """Get reaction roles for a message or all for guild."""
        cursor = self.conn.cursor()
        if message_id:
            cursor.execute("""
                SELECT * FROM reaction_roles 
                WHERE guild_id = ? AND message_id = ?
            """, (guild_id, message_id))
        else:
            cursor.execute("""
                SELECT * FROM reaction_roles WHERE guild_id = ?
            """, (guild_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def remove_reaction_role(self, guild_id: int, message_id: int, emoji: str):
        """Remove a reaction role."""
        cursor = self.conn.cursor()
        cursor.execute("""
            DELETE FROM reaction_roles 
            WHERE guild_id = ? AND message_id = ? AND emoji = ?
        """, (guild_id, message_id, emoji))
        self.conn.commit()
        return cursor.rowcount > 0
    
    # Leveling Methods
    def get_user_level(self, guild_id: int, user_id: int) -> Dict:
        """Get user level data."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM user_levels 
            WHERE guild_id = ? AND user_id = ?
        """, (guild_id, user_id))
        row = cursor.fetchone()
        
        if row:
            return dict(row)
        else:
            # Create default
            cursor.execute("""
                INSERT INTO user_levels (guild_id, user_id) VALUES (?, ?)
            """, (guild_id, user_id))
            self.conn.commit()
            return {'guild_id': guild_id, 'user_id': user_id, 'xp': 0, 'level': 1, 'total_messages': 0}
    
    def add_xp(self, guild_id: int, user_id: int, xp: int):
        """Add XP to a user."""
        cursor = self.conn.cursor()
        data = self.get_user_level(guild_id, user_id)
        new_xp = data['xp'] + xp
        new_level = self.calculate_level(new_xp)
        
        cursor.execute("""
            UPDATE user_levels 
            SET xp = ?, level = ?, total_messages = total_messages + 1
            WHERE guild_id = ? AND user_id = ?
        """, (new_xp, new_level, guild_id, user_id))
        self.conn.commit()
        
        leveled_up = new_level > data['level']
        return {'level': new_level, 'xp': new_xp, 'leveled_up': leveled_up}
    
    @staticmethod
    def calculate_level(xp: int) -> int:
        """Calculate level from XP (exponential: level = sqrt(xp/100))."""
        import math
        return int(math.sqrt(xp / 100)) + 1
    
    def get_leaderboard(self, guild_id: int, limit: int = 10) -> List[Dict]:
        """Get top users by XP."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM user_levels 
            WHERE guild_id = ? 
            ORDER BY xp DESC 
            LIMIT ?
        """, (guild_id, limit))
        return [dict(row) for row in cursor.fetchall()]
    
    # AFK Methods
    def set_afk(self, guild_id: int, user_id: int, message: str):
        """Set user as AFK."""
        cursor = self.conn.cursor()
        from datetime import datetime
        cursor.execute("""
            INSERT OR REPLACE INTO afk_users (guild_id, user_id, afk_message, afk_since)
            VALUES (?, ?, ?, ?)
        """, (guild_id, user_id, message, datetime.utcnow().isoformat()))
        self.conn.commit()
    
    def remove_afk(self, guild_id: int, user_id: int):
        """Remove user from AFK."""
        cursor = self.conn.cursor()
        cursor.execute("""
            DELETE FROM afk_users WHERE guild_id = ? AND user_id = ?
        """, (guild_id, user_id))
        self.conn.commit()
    
    def is_afk(self, guild_id: int, user_id: int) -> Optional[Dict]:
        """Check if user is AFK."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM afk_users 
            WHERE guild_id = ? AND user_id = ?
        """, (guild_id, user_id))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    # Scheduled Announcements
    def add_scheduled_announcement(self, guild_id: int, channel_id: int, message: str, interval_minutes: int):
        """Add a scheduled announcement."""
        cursor = self.conn.cursor()
        from datetime import datetime, timedelta
        next_run = (datetime.utcnow() + timedelta(minutes=interval_minutes)).isoformat()
        cursor.execute("""
            INSERT INTO scheduled_announcements 
            (guild_id, channel_id, message, interval_minutes, next_run)
            VALUES (?, ?, ?, ?, ?)
        """, (guild_id, channel_id, message, interval_minutes, next_run))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_due_announcements(self) -> List[Dict]:
        """Get announcements that are due to run."""
        cursor = self.conn.cursor()
        from datetime import datetime
        now = datetime.utcnow().isoformat()
        cursor.execute("""
            SELECT * FROM scheduled_announcements 
            WHERE enabled = 1 AND next_run <= ?
        """, (now,))
        return [dict(row) for row in cursor.fetchall()]
    
    def update_announcement_next_run(self, announcement_id: int):
        """Update next run time for an announcement."""
        cursor = self.conn.cursor()
        from datetime import datetime, timedelta
        cursor.execute("SELECT interval_minutes FROM scheduled_announcements WHERE id = ?", (announcement_id,))
        row = cursor.fetchone()
        if row:
            interval = row['interval_minutes']
            next_run = (datetime.utcnow() + timedelta(minutes=interval)).isoformat()
            cursor.execute("""
                UPDATE scheduled_announcements SET next_run = ? WHERE id = ?
            """, (next_run, announcement_id))
            self.conn.commit()
    
    # Auto-mod Config
    def get_automod_config(self, guild_id: int) -> Dict:
        """Get auto-mod configuration."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM automod_config WHERE guild_id = ?", (guild_id,))
        row = cursor.fetchone()
        
        if row:
            return dict(row)
        else:
            # Create default
            cursor.execute("""
                INSERT INTO automod_config (guild_id) VALUES (?)
            """, (guild_id,))
            self.conn.commit()
            return self.get_automod_config(guild_id)
    
    def update_automod_setting(self, guild_id: int, setting: str, value):
        """Update auto-mod setting."""
        cursor = self.conn.cursor()
        self.get_automod_config(guild_id)  # Ensure exists
        cursor.execute(f"UPDATE automod_config SET {setting} = ? WHERE guild_id = ?", (value, guild_id))
        self.conn.commit()
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

