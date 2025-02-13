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
    await embeds()
    await invoices()

async def refresh_table(table: str):
    if table == "Embeds":
        await embeds(True)
    elif table == "Invoices":
        await invoices(True) 

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

class SQLiteCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="refreshtable", description="Refreshes a SQLite table!")
    @app_commands.describe(table="What table should be refreshed?")
    @app_commands.default_permissions(administrator=True)
    async def refreshtable(self, interaction: discord.Interaction, table: Literal["Embeds", "Invoices"]) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)

        if await self.bot.is_owner(interaction.user):
            await refresh_table(table)
            embed = discord.Embed(description=f"Successfully refreshed the table **{table}**!", color=discord.Color.from_str(embed_color))
        else:
            embed = discord.Embed("You do not have permission to use this command!", color=discord.Color.red())
        
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(SQLiteCog(bot), guilds=[discord.Object(id=guild_id)])