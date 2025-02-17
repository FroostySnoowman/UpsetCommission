import discord
import yaml
import aiosqlite
import re
from discord import app_commands
from discord.ext import commands

with open('config.yml', 'r') as file:
    data = yaml.safe_load(file)

embed_color = data["General"]["EMBED_COLOR"]
embed_roles = data["Permissions"].get("EMBED_ROLES", [])

IMAGE_URL_REGEX = re.compile(r"^https?:\/\/.*\.(?:png|jpg|jpeg|gif|webp)$")

class EmbedTextInputModal(discord.ui.Modal):
    def __init__(self, embed_creator: "EmbedCreator", field_name: str, max_length: int):
        super().__init__(title=f"Set {field_name}", timeout=None)
        self.embed_creator = embed_creator
        self.field_name = field_name

        self.text_input = discord.ui.TextInput(
            label=f"Enter {field_name}",
            placeholder=f"Type the {field_name.lower()} here...",
            max_length=max_length,
            style=discord.TextStyle.short,
        )
        self.add_item(self.text_input)

    async def on_submit(self, interaction: discord.Interaction):
        value = self.text_input.value.strip()

        if "image" in self.field_name.lower():
            if value and not IMAGE_URL_REGEX.match(value):
                await interaction.response.send_message(f"❌ Invalid URL for {self.field_name}. Please enter a valid image link (png, jpg, jpeg, gif, webp).", ephemeral=True)
                return

        setattr(self.embed_creator, self.field_name.lower().replace(" ", "_"), value)

        embed = self.embed_creator.generate_embed()
        await interaction.response.edit_message(embed=embed, view=self.embed_creator)

class EmbedCreator(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.author = None
        self.title = None
        self.description = None
        self.footer = None
        self.author_image = None
        self.thumbnail_image = None
        self.large_image = None
        self.footer_image = None
        self.embed_color = embed_color

    def generate_embed(self):
        embed = discord.Embed(title=self.title or "Embed Builder", description=self.description or "Use the buttons to edit.", color=discord.Color.from_str(self.embed_color or embed_color))

        if self.author:
            embed.set_author(name=self.author, icon_url=self.author_image if IMAGE_URL_REGEX.match(self.author_image or "") else None)
        if self.footer:
            embed.set_footer(text=self.footer, icon_url=self.footer_image if IMAGE_URL_REGEX.match(self.footer_image or "") else None)
        if self.thumbnail_image and IMAGE_URL_REGEX.match(self.thumbnail_image):
            embed.set_thumbnail(url=self.thumbnail_image)
        if self.large_image and IMAGE_URL_REGEX.match(self.large_image):
            embed.set_image(url=self.large_image)

        return embed

    async def open_modal(self, interaction: discord.Interaction, field_name: str, max_length: int):
        await interaction.response.send_modal(EmbedTextInputModal(self, field_name, max_length))

    @discord.ui.button(label='Author Text', style=discord.ButtonStyle.blurple, custom_id='embed_creator:author')
    async def author_text_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.open_modal(interaction, "Author", 100)

    @discord.ui.button(label='Title', style=discord.ButtonStyle.blurple, custom_id='embed_creator:title')
    async def title_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.open_modal(interaction, "Title", 256)

    @discord.ui.button(label='Description', style=discord.ButtonStyle.blurple, custom_id='embed_creator:description')
    async def description_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.open_modal(interaction, "Description", 2048)

    @discord.ui.button(label='Footer', style=discord.ButtonStyle.blurple, custom_id='embed_creator:footer')
    async def footer_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.open_modal(interaction, "Footer", 200)

    @discord.ui.button(label='Author Image', style=discord.ButtonStyle.blurple, custom_id='embed_creator:image')
    async def image_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.open_modal(interaction, "Author Image", 2000)

    @discord.ui.button(label='Thumbnail Image', style=discord.ButtonStyle.blurple, custom_id='embed_creator:thumbnail')
    async def thumbnail_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.open_modal(interaction, "Thumbnail Image", 2000)

    @discord.ui.button(label='Large Image', style=discord.ButtonStyle.blurple, custom_id='embed_creator:large_image')
    async def large_image_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.open_modal(interaction, "Large Image", 2000)

    @discord.ui.button(label='Footer Image', style=discord.ButtonStyle.blurple, custom_id='embed_creator:footer_image')
    async def footer_image_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.open_modal(interaction, "Footer Image", 2000)

    @discord.ui.button(label='Save Embed', style=discord.ButtonStyle.green, custom_id='embed_creator:save')
    async def save_embed_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect("database.db") as db:
            await db.execute(
                """
                INSERT INTO embeds (title, description, author, footer, author_image, 
                thumbnail_image, large_image, footer_image, embed_color)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.title, self.description, self.author, self.footer,
                    self.author_image, self.thumbnail_image, self.large_image, self.footer_image, self.embed_color
                )
            )
            await db.commit()

        await interaction.response.send_message("✅ Embed saved successfully!", ephemeral=True)

    @discord.ui.button(label='Post Embed', style=discord.ButtonStyle.danger, custom_id='embed_creator:post')
    async def post_embed_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = self.generate_embed()
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("✅ Embed posted!", ephemeral=True)

class EmbedCog(commands.GroupCog, name="embed"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.bot.add_view(EmbedCreator())

    async def check_permissions(self, interaction: discord.Interaction) -> bool:
        user_roles = [role.id for role in interaction.user.roles]

        return any(role in user_roles for role in embed_roles)

    @app_commands.command(name="new", description="Creates a new embed")
    async def new(self, interaction: discord.Interaction) -> None:
        if not await self.check_permissions(interaction):
            embed = discord.Embed(title="No Permission", description="You do not have permission to use this command.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = discord.Embed(title="Embed Builder", description="Welcome to the **interactive embed builder**.\nUse the buttons below to build the embed, when you're done, click **Post Embed**!", color=discord.Color.blue())
        await interaction.response.send_message(embed=embed, view=EmbedCreator())

    @app_commands.command(name="post", description="Posts a stored embed from the database")
    async def post(self, interaction: discord.Interaction, embed_id: int) -> None:
        if not await self.check_permissions(interaction):
            embed = discord.Embed(title="No Permission", description="You do not have permission to use this command.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        async with aiosqlite.connect("database.db") as db:
            cursor = await db.execute("SELECT * FROM embeds WHERE id = ?", (embed_id,))
            embed_data = await cursor.fetchone()

        if not embed_data:
            await interaction.response.send_message("❌ Embed not found.", ephemeral=True)
            return

        embed = discord.Embed(title=embed_data[1], description=embed_data[2], color=discord.Color.from_str(embed_data[9]))

        if embed_data[3]:
            embed.set_author(name=embed_data[3], icon_url=embed_data[5])
        if embed_data[4]:
            embed.set_footer(text=embed_data[4], icon_url=embed_data[8])
        if embed_data[6]:
            embed.set_thumbnail(url=embed_data[6])
        if embed_data[7]:
            embed.set_image(url=embed_data[7])

        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("✅ Embed posted!", ephemeral=True)

    @app_commands.command(name="list", description="Lists all stored embeds")
    async def list_embeds(self, interaction: discord.Interaction) -> None:
        if not await self.check_permissions(interaction):
            embed = discord.Embed(title="No Permission", description="You do not have permission to use this command.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        async with aiosqlite.connect("database.db") as db:
            cursor = await db.execute("SELECT id, title FROM embeds")
            embeds = await cursor.fetchall()

        if not embeds:
            await interaction.response.send_message("❌ No stored embeds found.", ephemeral=True)
            return

        embed_list = "\n".join([f"**ID {embed[0]}**: {embed[1] or 'Untitled'}" for embed in embeds])
        await interaction.response.send_message(f"📋 **Stored Embeds:**\n{embed_list}", ephemeral=True)

    @app_commands.command(name="edit", description="Edits an existing message with a stored embed")
    async def edit(self, interaction: discord.Interaction, channel: discord.TextChannel, message_id: int, embed_id: int) -> None:
        if not await self.check_permissions(interaction):
            embed = discord.Embed(title="No Permission", description="You do not have permission to use this command.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        try:
            message = await channel.fetch_message(message_id)
        except discord.NotFound:
            await interaction.response.send_message("❌ Message not found.", ephemeral=True)
            return

        async with aiosqlite.connect("database.db") as db:
            cursor = await db.execute("SELECT * FROM embeds WHERE id = ?", (embed_id,))
            embed_data = await cursor.fetchone()

        if not embed_data:
            await interaction.response.send_message("❌ Embed not found.", ephemeral=True)
            return

        embed = discord.Embed(title=embed_data[1], description=embed_data[2], color=discord.Color.from_str(embed_data[9]))

        if embed_data[3]:
            embed.set_author(name=embed_data[3], icon_url=embed_data[5])
        if embed_data[4]:
            embed.set_footer(text=embed_data[4], icon_url=embed_data[8])
        if embed_data[6]:
            embed.set_thumbnail(url=embed_data[6])
        if embed_data[7]:
            embed.set_image(url=embed_data[7])

        await message.edit(embed=embed)
        await interaction.response.send_message("✅ Embed updated successfully!", ephemeral=True)

    @app_commands.command(name="delete", description="Deletes a stored embed or a message with an embed")
    async def delete(self, interaction: discord.Interaction, embed_id: int = None, channel: discord.TextChannel = None, message_id: int = None) -> None:
        if not await self.check_permissions(interaction):
            embed = discord.Embed(title="No Permission", description="You do not have permission to use this command.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if channel and message_id:
            try:
                message = await channel.fetch_message(message_id)
                await message.delete()
                await interaction.response.send_message("✅ Message deleted successfully!", ephemeral=True)
                return
            except discord.NotFound:
                await interaction.response.send_message("❌ Message not found.", ephemeral=True)
                return

        if embed_id:
            async with aiosqlite.connect("database.db") as db:
                cursor = await db.execute("SELECT * FROM embeds WHERE id = ?", (embed_id,))
                embed_data = await cursor.fetchone()

                if not embed_data:
                    await interaction.response.send_message("❌ Embed not found.", ephemeral=True)
                    return

                await db.execute("DELETE FROM embeds WHERE id = ?", (embed_id,))
                await db.commit()

            await interaction.response.send_message("✅ Embed deleted successfully!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Please specify either an embed ID or a channel & message ID.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(EmbedCog(bot))