import discord
import chat_exporter
import htmlmin
import yaml
import io
from discord import app_commands
from datetime import datetime
from discord.ext import commands

with open('config.yml', 'r') as file:
    data = yaml.safe_load(file)

guild_id = data["General"]["GUILD_ID"]
embed_color = data["General"]["EMBED_COLOR"]
ticket_roles = data["Permissions"].get("TICKET_ROLES", [])

class TicketModal(discord.ui.Modal):
    def __init__(self, category_key: str):
        title = f"{category_key.title()} Ticket"
        super().__init__(title=title)
        self.category_key = category_key
        self.inputs = {}

        for question in data["Tickets"][category_key]["QUESTIONS"]:
            text_input = discord.ui.TextInput(
                label=question["label"],
                style=discord.TextStyle.long,
                required=True,
                max_length=question["max_length"]
            )
            self.add_item(text_input)
            self.inputs[question["label"]] = text_input

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Ticket Creation", description="Loading...", color=discord.Color.from_str(embed_color))
        await interaction.response.send_message(embed=embed, ephemeral=True)

        category_id = data["Tickets"][self.category_key]["CATEGORY_ID"]
        added_roles = data["Tickets"][self.category_key].get("ADDED_ROLES", [])

        category_channel = interaction.guild.get_channel(category_id)

        if not category_channel:
            embed = discord.Embed(title="Ticket Creation", description="❌ Error: Ticket category channel not found!", color=discord.Color.from_str(embed_color))
            await interaction.edit_original_response(embed=embed, ephemeral=True)
            return

        username_prefix = interaction.user.name[:4].lower()
        ticket_channel = await category_channel.create_text_channel(f"{self.category_key.lower()}-{username_prefix}")

        await ticket_channel.set_permissions(interaction.guild.default_role,
            send_messages=False,
            read_messages=False)

        for role_id in added_roles:
            role = interaction.guild.get_role(role_id)
            if role:
                await ticket_channel.set_permissions(role,
                    send_messages=True,
                    read_messages=True,
                    add_reactions=True,
                    embed_links=True,
                    read_message_history=True,
                    external_emojis=True)

        await ticket_channel.set_permissions(interaction.user,
            send_messages=True,
            read_messages=True,
            add_reactions=True,
            embed_links=True,
            attach_files=True,
            read_message_history=True,
            external_emojis=True)

        embed = discord.Embed(title="Ticket Creation", description=f"The ticket has been created at {ticket_channel.mention}!", color=discord.Color.from_str(embed_color))
        await interaction.edit_original_response(embed=embed)

        embed = discord.Embed(description="Support will be with you shortly!\nThis ticket will close in 24 hours of inactivity.", color=discord.Color.from_str(embed_color))
        embed.set_footer(text="Close this ticket by clicking the 🔒 button.")

        responses = "\n".join([f"**{label}**: {field.value}" for label, field in self.inputs.items()])
        embed2 = discord.Embed(title="Responses", description=responses, color=discord.Color.from_str(embed_color))

        view = TicketsClose()
        await ticket_channel.send(content=interaction.user.mention, embeds=[embed, embed2], view=view)

class Tickets(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def create_ticket(self, interaction: discord.Interaction, category_key: str):
        modal = TicketModal(category_key)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='Quotes', style=discord.ButtonStyle.blurple, custom_id='tickets:quotes')
    async def quotes_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "QUOTES")

    @discord.ui.button(label='Apply', style=discord.ButtonStyle.green, custom_id='tickets:apply')
    async def apply_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "APPLY")

    @discord.ui.button(label='Support', style=discord.ButtonStyle.gray, custom_id='tickets:support')
    async def support_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "SUPPORT")

class TicketsClose(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Close Ticket', style=discord.ButtonStyle.danger, emoji="🔒", custom_id="tickets:close")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        first_message = [msg async for msg in interaction.channel.history(oldest_first=True, limit=1)]
        
        if not first_message or not first_message[0].mentions:
            await interaction.followup.send("❌ Could not determine the ticket creator.", ephemeral=True)
            return

        creator = first_message[0].mentions[0]
        timestamp = int(datetime.now().timestamp())

        transcript = await chat_exporter.export(
            interaction.channel,
            limit=500,
            tz_info="MST",
            military_time=False,
            fancy_times=True,
            bot=interaction.client,
        )

        if transcript is None:
            await interaction.followup.send("❌ Failed to create transcript.", ephemeral=True)
            return

        minified_transcript = htmlmin.minify(transcript, remove_empty_space=True)
        file_bytes = io.BytesIO(minified_transcript.encode())
        file_name = f"{interaction.channel.name}.html"

        archive_channel_id = data["Tickets"].get("ARCHIVE_CHANNEL_ID")
        archive_channel = interaction.guild.get_channel(archive_channel_id) if archive_channel_id else None

        embed = discord.Embed(title="📜 Ticket Transcript 📜", description=f"Creator: {creator.mention}\nClosed At: <t:{timestamp}:f>\nChannel: {interaction.channel.name}", color=discord.Color.from_str(embed_color))
        embed.set_footer(text="Download the file above and open it to view the transcript")
        embed.timestamp = datetime.now()

        if archive_channel:
            archive_file = discord.File(io.BytesIO(minified_transcript.encode()), filename=file_name)
            await archive_channel.send(embed=embed, file=archive_file)

        try:
            file_bytes.seek(0)
            user_file = discord.File(file_bytes, filename=file_name)
            await creator.send(embed=embed, file=user_file)
        except discord.Forbidden:
            pass

        await interaction.channel.delete()

class TicketCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.bot.add_view(Tickets())
        self.bot.add_view(TicketsClose())

    async def check_permissions(self, interaction: discord.Interaction) -> bool:
        user_roles = [role.id for role in interaction.user.roles]

        return any(role in user_roles for role in ticket_roles)

    @app_commands.command(name="panel", description="Sends the ticket panel")
    @app_commands.default_permissions(administrator=True)
    async def panel(self, interaction: discord.Interaction) -> None:
        if not await self.check_permissions(interaction):
            embed = discord.Embed(title="No Permission", description="You do not have permission to use this command.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        embed = discord.Embed(color=discord.Color.from_str(embed_color))
        embed.set_image(url="https://media.discordapp.net/attachments/1338546681683247146/1338890382985134141/TICKETS.PNG?ex=67ae0bd6&is=67acba56&hm=2471198875a29c1b78deb841e00a727b8c4d978b5401e0024be27f34f376f3df&=&format=webp&quality=lossless&width=1008&height=314")
        embed.set_footer(text="Orchard Studios - Open a Ticket to talk to a Representative!")
        await interaction.channel.send(embed=embed, view=Tickets())

        await interaction.response.send_message('Sent!', ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(TicketCog(bot))