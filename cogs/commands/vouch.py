import discord
import yaml
from discord import app_commands
from discord.ext import commands
from datetime import datetime

with open('config.yml', 'r') as file:
    data = yaml.safe_load(file)

embed_color = data["General"]["EMBED_COLOR"]
archive_channel_id = data["Tickets"].get("ARCHIVE_CHANNEL_ID")
vouch_channel_id = data["Vouches"].get("VOUCH_CHANNEL_ID")
vouch_roles = data["Permissions"].get("VOUCH_ROLES", [])

class VouchModal(discord.ui.Modal, title="Submit a Vouch/Review"):
    def __init__(self, ticket_channel: discord.TextChannel, rating: int):
        super().__init__()
        self.ticket_channel = ticket_channel
        self.rating = rating

        self.vouch_text = discord.ui.TextInput(
            label="Write your vouch/review",
            style=discord.TextStyle.long,
            required=True,
            max_length=2000
        )
        self.add_item(self.vouch_text)

    async def on_submit(self, interaction: discord.Interaction):
        stars = "⭐" * self.rating

        embed = discord.Embed(title="New Vouch", description=f"**A new vouch has been submitted!**", color=discord.Color.from_str(embed_color))
        embed.add_field(name="Rating", value=stars, inline=True)
        embed.add_field(name="Review", value=self.vouch_text.value, inline=True)
        embed.add_field(name="User", value=interaction.user.mention, inline=True)
        embed.set_footer(text=f"{interaction.guild.name}")
        embed.timestamp = datetime.now()

        if vouch_channel_id:
            vouch_channel = interaction.guild.get_channel(vouch_channel_id)
            if vouch_channel:
                await vouch_channel.send(embed=embed)

        await self.ticket_channel.send(embed=embed)

        embed = discord.Embed(title="Vouch Submitted", description="Your vouch has been submitted!", color=discord.Color.from_str(embed_color))
        embed.timestamp = datetime.now()

        await interaction.response.edit_message(embed=embed, view=None)

class VouchRatingDropdown(discord.ui.Select):
    def __init__(self, ticket_channel: discord.TextChannel):
        options = [
            discord.SelectOption(label="⭐", value="1"),
            discord.SelectOption(label="⭐⭐", value="2"),
            discord.SelectOption(label="⭐⭐⭐", value="3"),
            discord.SelectOption(label="⭐⭐⭐⭐", value="4"),
            discord.SelectOption(label="⭐⭐⭐⭐⭐", value="5"),
        ]
        super().__init__(placeholder="Select a rating (1-5)", options=options)
        self.ticket_channel = ticket_channel

    async def callback(self, interaction: discord.Interaction):
        rating = int(self.values[0])
        await interaction.response.send_modal(VouchModal(self.ticket_channel, rating))

class VouchButton(discord.ui.View):
    def __init__(self, ticket_channel: discord.TextChannel):
        super().__init__(timeout=None)
        self.add_item(VouchRatingDropdown(ticket_channel))

class VouchCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def check_permissions(self, interaction: discord.Interaction) -> bool:
        user_roles = [role.id for role in interaction.user.roles]

        return any(role in user_roles for role in vouch_roles)

    @app_commands.command(name="vouch", description="Submit a vouch/review inside a ticket channel.")
    async def vouch(self, interaction: discord.Interaction):
        if not await self.check_permissions(interaction):
            embed = discord.Embed(title="No Permission", description="You do not have permission to use this command.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if not any(category_key.lower() in interaction.channel.name.lower() for category_key in data["Tickets"].keys()):
            embed = discord.Embed(title="Error", description="This command can only be used inside a ticket channel!", color=discord.Color.from_str(embed_color))
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = discord.Embed(title="Submit a Vouch", description="Select a rating below to submit a vouch/review!", color=discord.Color.from_str(embed_color))
        embed.timestamp = datetime.now()

        await interaction.response.send_message(embed=embed, view=VouchButton(interaction.channel))

async def setup(bot: commands.Bot):
    await bot.add_cog(VouchCog(bot))