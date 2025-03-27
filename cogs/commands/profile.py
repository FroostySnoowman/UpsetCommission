import discord
import aiosqlite
import yaml
from discord import app_commands
from discord.ext import commands

with open('config.yml', 'r') as file:
    data = yaml.safe_load(file)

embed_color = data["General"]["EMBED_COLOR"]
freelancer_roles = data["Permissions"].get("FREELANCER_ROLES", [])

class ProfileModal(discord.ui.Modal):
    def __init__(self, category_key: str, placeholder: str = None):
        title = f"Set {category_key.title()}"
        super().__init__(title=title)
        self.category_key = category_key
        self.placeholder = placeholder

        self.text_input = discord.ui.TextInput(
            label=f"Set your {category_key} here",
            default=self.placeholder or "",
            max_length=1000,
            style=discord.TextStyle.short,
        )
        self.add_item(self.text_input)

    async def on_submit(self, interaction: discord.Interaction):
        user_input = self.text_input.value.strip()

        async with aiosqlite.connect('database.db') as db:
            await db.execute(
                f"""
                INSERT INTO profiles (member_id, {self.category_key})
                VALUES (?, ?)
                ON CONFLICT(member_id) DO UPDATE SET
                    {self.category_key} = excluded.{self.category_key}
                """,
                (interaction.user.id, user_input)
            )
            await db.commit()

        async with aiosqlite.connect('database.db') as db:
            async with db.execute(
                """
                SELECT portfolio, timezone, built_by_bit, description
                FROM profiles WHERE member_id = ?
                """, (interaction.user.id,)
            ) as cursor:
                row = await cursor.fetchone()

        portfolio, timezone, built_by_bit, description = row if row else (None, None, None, None)

        embed = discord.Embed(title=f"{interaction.user.name}'s Profile", color=discord.Color.from_str(embed_color))
        embed.add_field(name="🌎 Portfolio", value=portfolio or "Not Set", inline=False)
        embed.add_field(name="⏰ Timezone", value=timezone or "Not Set", inline=False)
        embed.add_field(name="🏪 BuiltByBit", value=built_by_bit or "Not Set", inline=False)
        embed.add_field(name="🧑‍💻 Description", value=description or "Not Set", inline=False)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)

        await interaction.response.edit_message(embed=embed)

class ProfileButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def open_modal(self, interaction: discord.Interaction, category_key: str):
        async with aiosqlite.connect('database.db') as db:
            async with db.execute("SELECT " + category_key + " FROM profiles WHERE member_id = ?", (interaction.user.id,)) as cursor:
                row = await cursor.fetchone()
                placeholder = row[0] if row else None

        await interaction.response.send_modal(ProfileModal(category_key, placeholder))

    @discord.ui.button(emoji='🌎', label='Portfolio', style=discord.ButtonStyle.blurple, custom_id='profile_buttons:1')
    async def portfolio(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.open_modal(interaction, "portfolio")

    @discord.ui.button(emoji='⏰', label='Timezone', style=discord.ButtonStyle.blurple, custom_id='profile_buttons:2')
    async def timezone(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.open_modal(interaction, "timezone")

    @discord.ui.button(emoji='🏪', label='BuiltByBit', style=discord.ButtonStyle.blurple, custom_id='profile_buttons:3')
    async def built_by_bit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.open_modal(interaction, "built_by_bit")

    @discord.ui.button(emoji='🧑‍💻', label='Description', style=discord.ButtonStyle.blurple, custom_id='profile_buttons:4')
    async def description(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.open_modal(interaction, "description")

class ProfileCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.bot.add_view(ProfileButtons())

    async def check_permissions(self, interaction: discord.Interaction) -> bool:
        user_roles = [role.id for role in interaction.user.roles]
        return any(role in user_roles for role in freelancer_roles)

    @app_commands.command(name="profile", description="Views the profile of a user")
    @app_commands.describe(member="The member to view the profile of")
    async def profile(self, interaction: discord.Interaction, member: discord.Member = None) -> None:
        if not member:
            member = interaction.user

        async with aiosqlite.connect('database.db') as db:
            async with db.execute(
                """
                SELECT portfolio, timezone, built_by_bit, description
                FROM profiles WHERE member_id = ?
                """, (member.id,)
            ) as cursor:
                row = await cursor.fetchone()

        portfolio, timezone, built_by_bit, description = row if row else (None, None, None, None)

        embed = discord.Embed(title=f"{member.name}'s Profile", color=discord.Color.from_str(embed_color))
        embed.add_field(name="🌎 Portfolio", value=portfolio or "Not Set", inline=False)
        embed.add_field(name="⏰ Timezone", value=timezone or "Not Set", inline=False)
        embed.add_field(name="🏪 BuiltByBit", value=built_by_bit or "Not Set", inline=False)
        embed.add_field(name="🧑‍💻 Description", value=description or "Not Set", inline=False)
        embed.set_thumbnail(url=member.display_avatar.url)

        if member.id == interaction.user.id:
            if await self.check_permissions(interaction):
                view = ProfileButtons()
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            else:
                embed.set_footer(text="You do not have permission to edit your profile.")
                await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ProfileCog(bot))