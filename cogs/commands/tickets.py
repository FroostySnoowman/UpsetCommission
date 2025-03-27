import discord
import aiosqlite
import yaml
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from cogs.functions.utils import close_ticket

with open('config.yml', 'r') as file:
    data = yaml.safe_load(file)

embed_color = data["General"]["EMBED_COLOR"]
ticket_roles = data["Permissions"].get("TICKET_ROLES", [])
commissions = data["Commissions"]
fee = data["Invoice"]["FEE"]

async def check_permissions(interaction: discord.Interaction) -> bool:
    user_roles = [role.id for role in interaction.user.roles]

    return any(role in user_roles for role in ticket_roles)

async def create_ticket(interaction: discord.Interaction, category_key: str, selected_role: int = None):
    modal = TicketModal(category_key, selected_role)
    await interaction.response.send_modal(modal)

class ClientButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Accept', emoji='✅', style=discord.ButtonStyle.gray, custom_id="client:accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

        async with aiosqlite.connect("database.db") as db:
            cursor = await db.execute("SELECT * FROM quotes WHERE message_id = ?", (interaction.message.id,))
            quote_data = await cursor.fetchone()

            if not quote_data:
                embed = discord.Embed(title="Error", description="❌ Could not find the quote data!", color=discord.Color.from_str(embed_color))
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            channel = interaction.client.get_channel(quote_data[1])
            if not channel:
                embed = discord.Embed(title="Error", description="❌ Could not find the commission channel!", color=discord.Color.from_str(embed_color))
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            cursor = await db.execute("SELECT * FROM commissions WHERE channel_id = ?", (channel.id,))
            commission_data = await cursor.fetchone()

            if not commission_data:
                embed = discord.Embed(title="Error", description="❌ Could not find the commission data!", color=discord.Color.from_str(embed_color))
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            freelancer = interaction.guild.get_member(quote_data[3])
            if not freelancer:
                embed = discord.Embed(title="Error", description="❌ Could not find the freelancer!", color=discord.Color.from_str(embed_color))
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            await db.execute('UPDATE commissions SET freelancer_id = ? WHERE channel_id = ?', (freelancer.id, channel.id))
            await db.commit()
            
            view = ClientButtons()
            view.accept.disabled = True
            view.decline.disabled = True

            embed = interaction.message.embeds[0]
            embed.title = "Accepted Quote"
            await interaction.message.edit(embed=embed, view=view)
            
            await channel.set_permissions(freelancer,
                send_messages=True,
                read_messages=True,
                add_reactions=True,
                embed_links=True,
                read_message_history=True,
                external_emojis=True)
            
            try:
                embed = discord.Embed(title="Quote Accepted", description=f"{freelancer.mention}, your quote for {channel.mention} has been accepted for **${quote_data[4]:.2f}**!", color=discord.Color.from_str(embed_color))
                
                embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
                embed.set_thumbnail(url=freelancer.display_avatar.url)

                embed.timestamp = datetime.now()

                await freelancer.send(embed=embed)
            except discord.Forbidden:
                pass

            cursor = await db.execute("SELECT * FROM quotes WHERE channel_id = ?", (channel.id,))
            quotes = await cursor.fetchall()

            for quote in quotes:
                if quote[2] == interaction.message.id:
                    continue

                try:
                    quote_message = await channel.fetch_message(quote[2])
                    await quote_message.delete()
                except:
                    continue
            
            embed = discord.Embed(title="Quote Accepted", description=f"{freelancer.mention} has been added to the commission!", color=discord.Color.from_str(embed_color))
            await interaction.channel.send(embed=embed)

    @discord.ui.button(label='Decline', emoji='❌', style=discord.ButtonStyle.gray, custom_id="client:decline")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

        async with aiosqlite.connect("database.db") as db:
            cursor = await db.execute("SELECT * FROM quotes WHERE message_id = ?", (interaction.message.id,))
            quote_data = await cursor.fetchone()

            if not quote_data:
                embed = discord.Embed(title="Error", description="❌ Could not find the quote data!", color=discord.Color.from_str(embed_color))
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            channel = interaction.client.get_channel(quote_data[1])
            if not channel:
                embed = discord.Embed(title="Error", description="❌ Could not find the commission channel!", color=discord.Color.from_str(embed_color))
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            cursor = await db.execute("SELECT * FROM commissions WHERE channel_id = ?", (channel.id,))
            commission_data = await cursor.fetchone()

            if not commission_data:
                embed = discord.Embed(title="Error", description="❌ Could not find the commission data!", color=discord.Color.from_str(embed_color))
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            freelancer = interaction.guild.get_member(quote_data[3])
            
            if freelancer:
                try:
                    embed = discord.Embed(title="Quote Declined", description=f"{freelancer.mention}, your quote for {channel.mention} has been declined.", color=discord.Color.from_str(embed_color))
                    await freelancer.send(embed=embed)
                except discord.Forbidden:
                    pass
            
            await interaction.message.delete()
            
            embed = discord.Embed(title="Quote Declined", description="The quote has been declined.", color=discord.Color.from_str(embed_color))
            await interaction.followup.send(embed=embed, ephemeral=True)

class QuestionModal(discord.ui.Modal, title='Answer a Question'):
    def __init__(self):
        super().__init__(timeout=None)

    reply = discord.ui.TextInput(
        label="What is your reply?",
        max_length=2048,
        style=discord.TextStyle.long,
    )

    async def on_submit(self, interaction: discord.Interaction):
        async with aiosqlite.connect("database.db") as db:
            cursor = await db.execute("SELECT * FROM questions WHERE message_id = ?", (interaction.message.id,))
            question_data = await cursor.fetchone()

            if not question_data:
                embed = discord.Embed(title="Error", description="❌ Could not find the question data!", color=discord.Color.from_str(embed_color))
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            freelancer = interaction.guild.get_member(question_data[3])
            if not freelancer:
                embed = discord.Embed(title="Error", description="❌ Could not find the freelancer!", color=discord.Color.from_str(embed_color))
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            view = QuestionButtons()
            view.reply.disabled = True

            embed = interaction.message.embeds[0]
            embed.title = f"Answered Question From {freelancer.name}"

            embed.clear_fields()
            embed.add_field(name="Question", value=question_data[4], inline=True)
            embed.add_field(name="Reply", value=self.reply.value, inline=True)

            await interaction.message.edit(embed=embed, view=view)
            
            try:
                embed = discord.Embed(title="New Reply", description=f"{freelancer.mention}, you have a new reply to your question!", color=discord.Color.from_str(embed_color))
                embed.timestamp = datetime.now()

                embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
                
                embed.add_field(name="Question", value=question_data[4], inline=True)
                embed.add_field(name="Reply", value=self.reply.value, inline=True)

                embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url if interaction.guild.icon else None)

                await freelancer.send(embed=embed)
            except discord.Forbidden:
                pass
                
            embed = discord.Embed(title="Reply Sent", description="Your reply has been sent!", color=discord.Color.from_str(embed_color))
            await interaction.response.send_message(embed=embed, ephemeral=True)

class QuestionButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Reply', emoji='❓', style=discord.ButtonStyle.gray, custom_id="question:reply")
    async def reply(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect("database.db") as db:
            cursor = await db.execute("SELECT * FROM commissions WHERE channel_id = ?", (interaction.channel.id,))
            commission_data = await cursor.fetchone()

            if not commission_data:
                embed = discord.Embed(title="Error", description="❌ Could not find the commission data!", color=discord.Color.from_str(embed_color))
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            if commission_data[4] != interaction.user.id:
                embed = discord.Embed(title="Error", description="❌ You are not the creator of this commission!", color=discord.Color.from_str(embed_color))
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
        
            await interaction.response.send_modal(QuestionModal())

class FreelancerModals(discord.ui.Modal):
    def __init__(self, key: str):
        title = "Enter a Quote" if key == "Quote" else "Ask a Question"
        super().__init__(title=title)
        self.key = key

        if key == "Quote":
            self.quote = discord.ui.TextInput(
                label="Enter a quote",
                max_length=10,
                style=discord.TextStyle.short,
            )
            self.message = discord.ui.TextInput(
                label="Enter a message",
                max_length=2048,
                style=discord.TextStyle.long,
                required=False,
            )
            self.add_item(self.quote)
            self.add_item(self.message)
        
        elif key == "Question":
            self.question = discord.ui.TextInput(
                label="Enter a question",
                max_length=2048,
                style=discord.TextStyle.long,
            )
            self.add_item(self.question)

    async def on_submit(self, interaction: discord.Interaction):
        async with aiosqlite.connect("database.db") as db:
            cursor = await db.execute("SELECT * FROM commissions WHERE freelancer_message_id = ?", (interaction.message.id,))
            commission_data = await cursor.fetchone()

            if not commission_data:
                embed = discord.Embed(title="Error", description="❌ Could not find the commission data!", color=discord.Color.from_str(embed_color))
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            channel = interaction.client.get_channel(commission_data[1])
            if not channel:
                embed = discord.Embed(title="Error", description="❌ Could not find the commission channel!", color=discord.Color.from_str(embed_color))
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            role_id = None
            for department in commissions:
                if department['channel'] == commission_data[2]:
                    role_id = department['role']
                    break
            
            if not role_id:
                embed = discord.Embed(title="Error", description="❌ Could not find the corresponding role!", color=discord.Color.from_str(embed_color))
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            cursor = await db.execute("SELECT * FROM profiles WHERE member_id = ?", (interaction.user.id,))
            freelancer_data = await cursor.fetchone()

            if not freelancer_data:
                embed = discord.Embed(title="Error", description="❌ You must have a profile to use this feature!", color=discord.Color.from_str(embed_color))
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            if self.key == "Quote":
                try:
                    quote_amount = float(self.quote.value)
                except ValueError:
                    embed = discord.Embed(title="Error", description="❌ Please enter a valid number for your quote!", color=discord.Color.from_str(embed_color))
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
                
                message_value = self.message.value
                fee_amount = quote_amount * (fee / 100)
                total_amount = quote_amount + fee_amount

                embed = discord.Embed(title="New Quote", color=discord.Color.from_str(embed_color))
                embed.timestamp = datetime.now()

                embed.set_thumbnail(url=interaction.user.display_avatar.url)
                embed.set_author(name=interaction.guild.name, icon_url=interaction.guild.icon.url if interaction.guild.icon else None)

                embed.add_field(name="Department", value=f"<@&{role_id}>", inline=True)
                embed.add_field(name="Freelancer", value=f"{interaction.user.mention} (@{interaction.user.name})", inline=True)
                embed.add_field(name="Portfolio", value=f"{freelancer_data[2] if freelancer_data[2] else 'N/A'}", inline=True)
                embed.add_field(name="Timezone", value=f"{freelancer_data[3] if freelancer_data[3] else 'N/A'}", inline=True)
                embed.add_field(name="BuiltByBit", value=f"{freelancer_data[4] if freelancer_data[4] else 'N/A'}", inline=True)
                embed.add_field(name="Description", value=f"{freelancer_data[5] if freelancer_data[5] else 'N/A'}", inline=True)

                embed.add_field(name="Quote Amount", value=f"${quote_amount:.2f}", inline=True)
                embed.add_field(name=f"PayPal Fee ({fee:.2f}%)", value=f"${fee_amount:.2f}", inline=True)
                embed.add_field(name="Total Amount", value=f"${total_amount:.2f}", inline=True)
                
                if message_value:
                    embed.add_field(name="Message", value=message_value, inline=False)
                
                embed.set_footer(text="Use the buttons to interact with this quote.", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)

                msg = await channel.send(content=f"<@{commission_data[4]}>", embed=embed, view=ClientButtons())

                await db.execute(
                    """
                    INSERT INTO quotes (channel_id, message_id, freelancer_id, amount)
                    VALUES (?, ?, ?, ?)
                    """,
                    (commission_data[1], msg.id, interaction.user.id, quote_amount)
                )
                await db.commit()

                embed = discord.Embed(title="Quote Sent", description="Your quote has been sent!", color=discord.Color.from_str(embed_color))
                await interaction.response.send_message(embed=embed, ephemeral=True)
            
            elif self.key == "Question":
                question_value = self.question.value

                embed = discord.Embed(title=f"New Question From {interaction.user.name}", color=discord.Color.from_str(embed_color))
                embed.timestamp = datetime.now()

                embed.set_thumbnail(url=interaction.user.display_avatar.url)
                embed.set_author(name=interaction.guild.name, icon_url=interaction.guild.icon.url if interaction.guild.icon else None)

                embed.add_field(name="Question", value=question_value, inline=False)

                embed.set_footer(text="Use the buttons to interact with this question.", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)

                msg = await channel.send(content=f"<@{commission_data[4]}>", embed=embed, view=QuestionButtons())

                await db.execute(
                    """
                    INSERT INTO questions (channel_id, message_id, freelancer_id, question)
                    VALUES (?, ?, ?, ?)
                    """,
                    (commission_data[1], msg.id, interaction.user.id, question_value)
                )
                await db.commit()

                embed = discord.Embed(title="Question Sent", description="Your question has been sent!", color=discord.Color.from_str(embed_color))
                await interaction.response.send_message(embed=embed, ephemeral=True)

class FreelancerButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Quote', emoji='💰', style=discord.ButtonStyle.red, custom_id="freelancer:quote")
    async def quote(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect("database.db") as db:
            cursor = await db.execute("SELECT * FROM commissions WHERE freelancer_message_id = ?", (interaction.message.id,))
            commission_data = await cursor.fetchone()

            if not commission_data:
                embed = discord.Embed(title="Error", description="❌ Could not find the commission data!", color=discord.Color.from_str(embed_color))
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            role_id = None
            for department in commissions:
                if department['channel'] == commission_data[2]:
                    role_id = department['role']
                    break
            
            if not role_id:
                embed = discord.Embed(title="Error", description="❌ Could not find the role for this commission!", color=discord.Color.from_str(embed_color))
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            role = interaction.guild.get_role(role_id)
            if not role:
                embed = discord.Embed(title="Error", description="❌ Could not find the role for this commission!", color=discord.Color.from_str(embed_color))
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            if role not in interaction.user.roles:
                embed = discord.Embed(title="Error", description=f"❌ You must have the {role.mention} role to send a quote!", color=discord.Color.from_str(embed_color))
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            await interaction.response.send_modal(FreelancerModals("Quote"))

    @discord.ui.button(label='Ask Question', emoji='❓', style=discord.ButtonStyle.gray, custom_id="freelancer:question")
    async def question(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect("database.db") as db:
            cursor = await db.execute("SELECT * FROM commissions WHERE freelancer_message_id = ?", (interaction.message.id,))
            commission_data = await cursor.fetchone()

            if not commission_data:
                embed = discord.Embed(title="Error", description="❌ Could not find the commission data!", color=discord.Color.from_str(embed_color))
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            role_id = None
            for department in commissions:
                if department['channel'] == commission_data[2]:
                    role_id = department['role']
                    break
            
            if not role_id:
                embed = discord.Embed(title="Error", description="❌ Could not find the role for this commission!", color=discord.Color.from_str(embed_color))
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            role = interaction.guild.get_role(role_id)
            if not role:
                embed = discord.Embed(title="Error", description="❌ Could not find the role for this commission!", color=discord.Color.from_str(embed_color))
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            if role not in interaction.user.roles:
                embed = discord.Embed(title="Error", description=f"❌ You must have the {role.mention} role to ask a question!", color=discord.Color.from_str(embed_color))
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            await interaction.response.send_modal(FreelancerModals("Question"))

class CommissionDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=commission["department"],
                value=str(commission["role"]),
            )
            for commission in commissions
        ]
        super().__init__(
            placeholder="Select a department...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        selected_role = int(self.values[0])
        await create_ticket(interaction, "QUOTES", selected_role)

class CommissionView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.add_item(CommissionDropdown())

class TicketModal(discord.ui.Modal):
    def __init__(self, category_key: str, selected_role: int = None):
        title = f"{category_key.title()} Ticket"
        super().__init__(title=title)
        self.category_key = category_key
        self.selected_role = selected_role
        self.inputs = {}

        for question in data["Tickets"][category_key]["QUESTIONS"]:
            style = discord.TextStyle.long if question.get("style", "long") == "long" else discord.TextStyle.short

            text_input = discord.ui.TextInput(
                label=question["label"],
                style=style,
                required=True,
                max_length=question["max_length"]
            )
            self.add_item(text_input)
            self.inputs[question["label"]] = text_input

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Ticket Creation", description="Loading...", color=discord.Color.from_str(embed_color))
        if self.category_key == "QUOTES":
            await interaction.response.edit_message(embed=embed, view=None)
        else:
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

        if self.category_key == "QUOTES":
            channel_id = next((commission["channel"] for commission in commissions if commission["role"] == self.selected_role), None)
            if channel_id is None:
                embed = discord.Embed(title="Ticket Creation", description="❌ Error: Could not find the commission channel!", color=discord.Color.from_str(embed_color))
                await ticket_channel.send(embed=embed)
                return
            
            commission_channel = interaction.guild.get_channel(channel_id)
            if not commission_channel:
                embed = discord.Embed(title="Ticket Creation", description="❌ Error: Could not find the commission channel!", color=discord.Color.from_str(embed_color))
                await ticket_channel.send(embed=embed)
                return

            selected_role = interaction.guild.get_role(self.selected_role)
            if not selected_role:
                embed = discord.Embed(title="Ticket Creation", description="❌ Error: Could not find the department role!", color=discord.Color.from_str(embed_color))
                await ticket_channel.send(embed=embed)
                return
            
            embed = discord.Embed(title="New Commission", description=f"**Posted**: <t:{int(datetime.now().timestamp())}:R>", color=discord.Color.from_str(embed_color))
            
            for question in data["Tickets"][self.category_key]["QUESTIONS"]:
                if "reference" in question:
                    reference = question["reference"]
                    response = self.inputs[question["label"]].value
                    embed.add_field(name=reference, value=response, inline=False)
            
            freelancer_message = await commission_channel.send(content=selected_role.mention, embed=embed, view=FreelancerButtons())

            async with aiosqlite.connect('database.db') as db:
                await db.execute(
                    """
                    INSERT INTO commissions (channel_id, freelancer_channel_id, freelancer_message_id, creator_id)
                    VALUES (?, ?, ?, ?)
                    """,
                    (ticket_channel.id, commission_channel.id, freelancer_message.id, interaction.user.id)
                )
                await db.commit()

class Tickets(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Quotes', style=discord.ButtonStyle.blurple, custom_id='tickets:quotes')
    async def quotes_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="Select a Department", description="Please select a department to continue.", color=discord.Color.from_str(embed_color))
        await interaction.response.send_message(embed=embed, view=CommissionView(), ephemeral=True)

    @discord.ui.button(label='Apply', style=discord.ButtonStyle.green, custom_id='tickets:apply')
    async def apply_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await create_ticket(interaction, "APPLY")

    @discord.ui.button(label='Support', style=discord.ButtonStyle.gray, custom_id='tickets:support')
    async def support_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await create_ticket(interaction, "SUPPORT")

class TicketsClose(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Close Ticket', style=discord.ButtonStyle.danger, emoji="🔒", custom_id="tickets:close")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

        async with aiosqlite.connect('database.db') as db:
            cursor = await db.execute("SELECT * FROM commissions WHERE channel_id = ?", (interaction.channel.id,))
            commission_data = await cursor.fetchone()

            if commission_data and commission_data[4] != interaction.user.id:
                if not await check_permissions(interaction):
                    embed = discord.Embed(title="Error", description="❌ You cannot close this ticket. You are not a staff member or the creator of the commission!", color=discord.Color.from_str(embed_color))
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return
        
        await close_ticket(interaction)

class TicketCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.bot.add_view(Tickets())
        self.bot.add_view(TicketsClose())
        self.bot.add_view(FreelancerButtons())
        self.bot.add_view(ClientButtons())
        self.bot.add_view(QuestionButtons())

    @app_commands.command(name="panel", description="Sends the ticket panel")
    @app_commands.default_permissions(administrator=True)
    async def panel(self, interaction: discord.Interaction) -> None:
        if not await check_permissions(interaction):
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
        if not await check_permissions(interaction):
            embed = discord.Embed(title="No Permission", description="You do not have permission to use this command.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        embed = discord.Embed(color=discord.Color.from_str(embed_color))
        embed.set_image(url="https://media.discordapp.net/attachments/1338546681683247146/1338890382985134141/TICKETS.PNG?ex=67ae0bd6&is=67acba56&hm=2471198875a29c1b78deb841e00a727b8c4d978b5401e0024be27f34f376f3df&=&format=webp&quality=lossless&width=1008&height=314")
        embed.set_footer(text="Orchard Studios - Open a Ticket to talk to a Representative!")
        await interaction.response.send_message(embed=embed, view=Tickets(), ephemeral=True)

    @app_commands.command(name="close", description="Closes a ticket")
    async def close(self, interaction: discord.Interaction) -> None:
        if not await check_permissions(interaction):
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
        if not await check_permissions(interaction):
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
        if not await check_permissions(interaction):
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
        if not await check_permissions(interaction):
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