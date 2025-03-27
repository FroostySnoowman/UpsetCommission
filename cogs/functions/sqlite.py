import discord
import aiosqlite
import sqlite3
import yaml
from discord.ext import commands
from discord import app_commands
from typing import Literal

with open('config.yml', 'r') as file:
    data = yaml.safe_load(file)

guild_id = data["General"]["GUILD_ID"]
embed_color = data["General"]["EMBED_COLOR"]

async def check_tables():
    await commissions()
    await embeds()
    await invoices()
    await profiles()
    await wallets()
    await withdrawals()
    await questions()
    await quotes()

async def refresh_table(table: str):
    if table == "Commissions":
        await commissions(True)
    if table == "Embeds":
        await embeds(True)
    elif table == "Invoices":
        await invoices(True) 
    elif table == "Profiles":
        await profiles(True)
    elif table == "Wallets":
        await wallets(True)
    elif table == "Withdrawals":
        await withdrawals(True)
    elif table == "Questions":
        await questions(True)
    elif table == "Quotes":
        await quotes(True)

async def embeds(delete: bool = False):
    async with aiosqlite.connect('database.db') as db:
        if delete:
            try:
                await db.execute('DROP TABLE embeds')
                await db.commit()
            except sqlite3.OperationalError:
                pass

        try:
            await db.execute('SELECT * FROM embeds')
        except sqlite3.OperationalError:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS embeds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    description TEXT,
                    author TEXT,
                    footer TEXT,
                    author_image TEXT,
                    thumbnail_image TEXT,
                    large_image TEXT,
                    footer_image TEXT,
                    embed_color TEXT
                )
            """)
            await db.commit()

async def invoices(delete: bool = False):
    async with aiosqlite.connect('database.db') as db:
        if delete:
            try:
                await db.execute('DROP TABLE invoices')
                await db.commit()
            except sqlite3.OperationalError:
                pass

        try:
            await db.execute('SELECT * FROM invoices')
        except sqlite3.OperationalError:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS invoices (
                    channel_id INTEGER,
                    message_id INTEGER,
                    invoice_id INTEGER,
                    amount INTEGER
                )
            """)
            await db.commit()

async def profiles(delete: bool = False):
    async with aiosqlite.connect('database.db') as db:
        if delete:
            try:
                await db.execute('DROP TABLE profiles')
                await db.commit()
            except aiosqlite.OperationalError:
                pass

        try:
            await db.execute('SELECT * FROM profiles')
        except aiosqlite.OperationalError:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    member_id INTEGER UNIQUE,
                    portfolio TEXT DEFAULT NULL,
                    timezone TEXT DEFAULT NULL,
                    built_by_bit TEXT DEFAULT NULL,
                    description TEXT DEFAULT NULL
                )
            """)
            await db.commit()

async def wallets(delete: bool = False):
    async with aiosqlite.connect('database.db') as db:
        if delete:
            try:
                await db.execute('DROP TABLE wallets')
                await db.commit()
            except aiosqlite.OperationalError:
                pass

        try:
            await db.execute('SELECT * FROM wallets')
        except aiosqlite.OperationalError:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS wallets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    member_id INTEGER UNIQUE,
                    paypal TEXT DEFAULT NULL,
                    amount INTEGER DEFAULT 0
                )
            """)
            await db.commit()

async def commissions(delete: bool = False):
    async with aiosqlite.connect('database.db') as db:
        if delete:
            try:
                await db.execute('DROP TABLE commissions')
                await db.commit()
            except aiosqlite.OperationalError:
                pass

        try:
            await db.execute('SELECT * FROM commissions')
        except aiosqlite.OperationalError:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS commissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER UNIQUE,
                    freelancer_channel_id INTEGER,
                    freelancer_message_id INTEGER,
                    creator_id INTEGER,
                    freelancer_id INTEGER DEFAULT NULL,
                    amount INTEGER DEFAULT 0
                )
            """)
            await db.commit()

async def questions(delete: bool = False):
    async with aiosqlite.connect('database.db') as db:
        if delete:
            try:
                await db.execute('DROP TABLE questions')
                await db.commit()
            except aiosqlite.OperationalError:
                pass

        try:
            await db.execute('SELECT * FROM questions')
        except aiosqlite.OperationalError:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER,
                    message_id INTEGER,
                    freelancer_id INTEGER,
                    question TEXT
                )
            """)
            await db.commit()

async def quotes(delete: bool = False):
    async with aiosqlite.connect('database.db') as db:
        if delete:
            try:
                await db.execute('DROP TABLE quotes')
                await db.commit()
            except aiosqlite.OperationalError:
                pass

        try:
            await db.execute('SELECT * FROM quotes')
        except aiosqlite.OperationalError:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS quotes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER,
                    message_id INTEGER,
                    freelancer_id INTEGER,
                    amount INTEGER
                )
            """)
            await db.commit()

async def withdrawals(delete: bool = False):
    async with aiosqlite.connect('database.db') as db:
        if delete:
            try:
                await db.execute('DROP TABLE withdrawals')
                await db.commit()
            except aiosqlite.OperationalError:
                pass

        try:
            await db.execute('SELECT * FROM withdrawals')
        except aiosqlite.OperationalError:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS withdrawals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER,
                    freelancer_id INTEGER,
                    amount INTEGER
                )
            """)
            await db.commit()

class SQLiteCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="refreshtable", description="Refreshes a SQLite table!")
    @app_commands.describe(table="What table should be refreshed?")
    @app_commands.default_permissions(administrator=True)
    async def refreshtable(self, interaction: discord.Interaction, table: Literal["Commissions", "Embeds", "Invoices", "Profiles", "Wallets", "Withdrawals", "Questions", "Quotes"]) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)

        if await self.bot.is_owner(interaction.user):
            await refresh_table(table)
            embed = discord.Embed(description=f"Successfully refreshed the table **{table}**!", color=discord.Color.from_str(embed_color))
        else:
            embed = discord.Embed("You do not have permission to use this command!", color=discord.Color.red())
        
        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(SQLiteCog(bot))