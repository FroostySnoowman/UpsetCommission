import discord
import yaml
from discord import app_commands
from discord.ext import commands
from cogs.functions.utils import close_ticket

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
        
        await close_ticket(interaction)

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

    @app_commands.command(name="open", description="Opens a ticket")
    @app_commands.default_permissions(administrator=True)
    async def panel(self, interaction: discord.Interaction) -> None:
        if not await self.check_permissions(interaction):
            embed = discord.Embed(title="No Permission", description="You do not have permission to use this command.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        embed = discord.Embed(color=discord.Color.from_str(embed_color))
        embed.set_image(url="https://media.discordapp.net/attachments/1338546681683247146/1338890382985134141/TICKETS.PNG?ex=67ae0bd6&is=67acba56&hm=2471198875a29c1b78deb841e00a727b8c4d978b5401e0024be27f34f376f3df&=&format=webp&quality=lossless&width=1008&height=314")
        embed.set_footer(text="Orchard Studios - Open a Ticket to talk to a Representative!")
        await interaction.response.send_message(embed=embed, view=Tickets(), ephemeral=True)

    @app_commands.command(name="close", description="Closes a ticket")
    async def close(self, interaction: discord.Interaction) -> None:
        if not await self.check_permissions(interaction):
            embed = discord.Embed(title="No Permission", description="You do not have permission to use this command.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if not any(category_key.lower() in interaction.channel.name.lower() for category_key in data["Tickets"].keys()):
            embed = discord.Embed(title="Error", description="This command can only be used inside a ticket channel!", color=discord.Color.from_str(embed_color))
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        await interaction.response.defer(thinking=True)
        
        await close_ticket(interaction)

    @app_commands.command(name="add", description="Adds a member to a ticket")
    async def add(self, interaction: discord.Interaction, member: discord.Member) -> None:
        if not await self.check_permissions(interaction):
            embed = discord.Embed(title="No Permission", description="You do not have permission to use this command.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if not any(category_key.lower() in interaction.channel.name.lower() for category_key in data["Tickets"].keys()):
            embed = discord.Embed(title="Error", description="This command can only be used inside a ticket channel!", color=discord.Color.from_str(embed_color))
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        await interaction.channel.set_permissions(member,
            send_messages=True,
            read_messages=True,
            add_reactions=True,
            embed_links=True,
            attach_files=True,
            read_message_history=True,
            external_emojis=True)
        
        embed = discord.Embed(title="Member Added", description=f"{member.mention} has been added to the ticket!", color=discord.Color.from_str(embed_color))
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="remove", description="Removes a member from a ticket")
    async def remove(self, interaction: discord.Interaction, member: discord.Member) -> None:
        if not await self.check_permissions(interaction):
            embed = discord.Embed(title="No Permission", description="You do not have permission to use this command.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if not any(category_key.lower() in interaction.channel.name.lower() for category_key in data["Tickets"].keys()):
            embed = discord.Embed(title="Error", description="This command can only be used inside a ticket channel!", color=discord.Color.from_str(embed_color))
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        await interaction.channel.set_permissions(member,
            send_messages=False,
            read_messages=False,
            add_reactions=False,
            embed_links=False,
            attach_files=False,
            read_message_history=False,
            external_emojis=False)
        
        embed = discord.Embed(title="Member Removed", description=f"{member.mention} has been removed from the ticket!", color=discord.Color.from_str(embed_color))
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="private", description="Makes the ticket private")
    async def private(self, interaction: discord.Interaction) -> None:
        if not await self.check_permissions(interaction):
            embed = discord.Embed(title="No Permission", description="You do not have permission to use this command.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if not any(category_key.lower() in interaction.channel.name.lower() for category_key in data["Tickets"].keys()):
            embed = discord.Embed(title="Error", description="This command can only be used inside a ticket channel!", color=discord.Color.from_str(embed_color))
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        overwrites = interaction.channel.overwrites
        
        new_overwrites = {target: perms for target, perms in overwrites.items() if not isinstance(target, discord.Member)}
        
        await interaction.channel.edit(overwrites=new_overwrites)
        
        embed = discord.Embed(title="Ticket Privated", description="This ticket is now private.", color=discord.Color.from_str(embed_color))
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(TicketCog(bot))