import discord
import aiosqlite
import yaml
from discord import app_commands
from discord.ext import commands
from datetime import datetime

with open('config.yml', 'r') as file:
    data = yaml.safe_load(file)

embed_color = data["General"]["EMBED_COLOR"]
freelancer_roles = data["Permissions"].get("FREELANCER_ROLES", [])
wallet_admin_roles = data["Permissions"].get("WALLET_ADMIN_ROLES", [])
withdraw_channel_id = data["Tickets"]["WITHDRAW_CHANNEL_ID"]

class AdminWalletButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Accept', style=discord.ButtonStyle.green, custom_id='admin_wallet:accept')
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect('database.db') as db:
            cursor = await db.execute("SELECT * FROM withdrawals WHERE message_id = ?", (interaction.message.id,))
            withdrawal_data = await cursor.fetchone()
            
            if not withdrawal_data:
                embed = discord.Embed(title="Error", description="This withdrawal request does not exist.", color=discord.Color.from_str(embed_color))
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            await db.execute('DELETE FROM withdrawals WHERE message_id = ?', (interaction.message.id,))
            await db.commit()

            view = AdminWalletButtons()
            view.accept.disabled = True
            view.deny.disabled = True

            embed = interaction.message.embeds[0]
            embed.title = "Withdrawal Processed"

            await interaction.message.edit(embed=embed, view=view)

            embed = discord.Embed(title="Withdrawal Processed", description=f"The withdrawal request for `${withdrawal_data[3]:.2f}` has been processed.", color=discord.Color.from_str(embed_color))
            await interaction.response.send_message(embed=embed, ephemeral=True)

            freelancer = interaction.guild.get_member(withdrawal_data[2])
            if freelancer:
                try:
                    embed = discord.Embed(title="Withdrawal Denied", description=f"Your withdrawal request for `${withdrawal_data[3]:.2f}` has been processed.", color=discord.Color.from_str(embed_color))
                    await freelancer.send(embed=embed)
                except:
                    pass

    @discord.ui.button(label='Deny', style=discord.ButtonStyle.red, custom_id='admin_wallet:deny')
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect('database.db') as db:
            cursor = await db.execute("SELECT * FROM withdrawals WHERE message_id = ?", (interaction.message.id,))
            withdrawal_data = await cursor.fetchone()
            
            if not withdrawal_data:
                embed = discord.Embed(title="Error", description="This withdrawal request does not exist.", color=discord.Color.from_str(embed_color))
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            await db.execute('DELETE FROM withdrawals WHERE message_id = ?', (interaction.message.id,))
            await db.commit()

            view = AdminWalletButtons()
            view.accept.disabled = True
            view.deny.disabled = True

            embed = interaction.message.embeds[0]
            embed.title = "Withdrawal Denied"

            await interaction.message.edit(embed=embed, view=view)

            embed = discord.Embed(title="Withdrawal Denied", description=f"The withdrawal request for `${withdrawal_data[3]:.2f}` has been denied.", color=discord.Color.from_str(embed_color))
            await interaction.response.send_message(embed=embed, ephemeral=True)

            freelancer = interaction.guild.get_member(withdrawal_data[2])
            if freelancer:
                try:
                    embed = discord.Embed(title="Withdrawal Denied", description=f"Your withdrawal request for `${withdrawal_data[3]:.2f}` has been denied.", color=discord.Color.from_str(embed_color))
                    await freelancer.send(embed=embed)
                except:
                    pass

class WalletModal(discord.ui.Modal):
    def __init__(self, interaction: discord.Interaction, paypal: str = None):
        title = "Set PayPal Email"
        super().__init__(title=title)
        self.interaction = interaction
        self.paypal = paypal

        self.text_input = discord.ui.TextInput(
            label="Enter your PayPal email",
            default=self.paypal or "",
            max_length=1000,
            style=discord.TextStyle.short,
        )
        self.add_item(self.text_input)

    async def on_submit(self, interaction: discord.Interaction):
        paypal_email = self.text_input.value.strip()

        async with aiosqlite.connect('database.db') as db:
            await db.execute(
                """
                INSERT INTO wallets (member_id, paypal)
                VALUES (?, ?)
                ON CONFLICT(member_id) DO UPDATE SET
                    paypal = excluded.paypal
                """,
                (interaction.user.id, paypal_email)
            )
            await db.commit()

            async with db.execute(
                "SELECT * FROM wallets WHERE member_id = ?", (interaction.user.id,)
            ) as cursor:
                row = await cursor.fetchone()

                balance = row[3]

                embed = discord.Embed(title="Manage Your Wallet", color=discord.Color.from_str(embed_color))
                embed.add_field(name="Balance", value=f"`${balance:.2f}`", inline=False)
                embed.add_field(name="PayPal", value=f"`{paypal_email}`", inline=False)

                embed.set_thumbnail(url=interaction.user.display_avatar.url)

                embed.set_author(name=interaction.guild.name, icon_url=interaction.guild.icon.url if interaction.guild.icon else None)

                await interaction.response.edit_message(embed=embed, view=WalletButtons())

class WalletButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='PayPal', style=discord.ButtonStyle.blurple, custom_id='wallet_buttons:paypal')
    async def paypal(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect('database.db') as db:
            async with db.execute(
                "SELECT paypal FROM wallets WHERE member_id = ?", (interaction.user.id,)
            ) as cursor:
                row = await cursor.fetchone()
                placeholder = row[0] if row else None

        await interaction.response.send_modal(WalletModal(interaction, placeholder))

    @discord.ui.button(label='Withdraw', style=discord.ButtonStyle.green, custom_id='wallet_buttons:withdraw')
    async def withdraw(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect('database.db') as db:
            async with db.execute(
                "SELECT * FROM wallets WHERE member_id = ?", (interaction.user.id,)
            ) as cursor:
                row = await cursor.fetchone()

                if row[3] <= 0:
                    embed = discord.Embed(title="Withdrawal Failed", description="You do not have enough funds to withdraw.", color=discord.Color.from_str(embed_color))
                    await interaction.response.edit_message(embed=embed, view=None)
                    return

                withdraw_channel = interaction.guild.get_channel(withdraw_channel_id)
                embed = discord.Embed(title="Withdraw Requested", description=f"{interaction.user.mention} ({interaction.user.name} | {interaction.user.id}) has requested a withdrawal of `${row[3]:.2f}`.", color=discord.Color.from_str(embed_color))
                embed.timestamp = datetime.now()

                embed.set_footer(text="Please review the request and process it accordingly.")

                embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
                
                msg = await withdraw_channel.send(embed=embed, view=AdminWalletButtons())

                await db.execute('UPDATE wallets SET amount = 0 WHERE member_id = ?', (interaction.user.id,))
                await db.execute(
                    """
                    INSERT INTO withdrawals (message_id, freelancer_id, amount)
                    VALUES (?, ?, ?)
                    """,
                    (msg.id, interaction.user.id, row[3])
                )
                await db.commit()

                embed = discord.Embed(title="Withdraw Requested", description=f"Your withdrawal request has been submitted for `${row[3]:.2f}`. Please allow up to 24 hours for processing.", color=discord.Color.from_str(embed_color))
                embed.timestamp = datetime.now()
                
                embed.set_footer(text="You will receive a confirmation message once the withdrawal has been processed.")

                embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)

                await interaction.response.edit_message(embed=embed, view=None)

class WalletCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.bot.add_view(WalletButtons())
        self.bot.add_view(AdminWalletButtons())

    async def check_freelancer_roles(self, interaction: discord.Interaction) -> bool:
        user_roles = [role.id for role in interaction.user.roles]
        return any(role in user_roles for role in freelancer_roles)

    async def check_admin_roles(self, interaction: discord.Interaction) -> bool:
        user_roles = [role.id for role in interaction.user.roles]
        return any(role in user_roles for role in wallet_admin_roles)

    @app_commands.command(name="wallet", description="Set or view PayPal email")
    @app_commands.describe(member="The member to view the PayPal email of (admins only)")
    async def wallet(self, interaction: discord.Interaction, member: discord.Member = None) -> None:
        if member is None:
            if await self.check_freelancer_roles(interaction):
                async with aiosqlite.connect('database.db') as db:
                    async with db.execute(
                        "SELECT * FROM wallets WHERE member_id = ?", (interaction.user.id,)
                    ) as cursor:
                        row = await cursor.fetchone()

                        if not row:
                            paypal = "N/A"
                            balance = 0
                        else:
                            paypal = row[2]
                            balance = row[3]

                        embed = discord.Embed(title="Manage Your Wallet", color=discord.Color.from_str(embed_color))
                        embed.add_field(name="Balance", value=f"`${balance:.2f}`", inline=False)
                        embed.add_field(name="PayPal", value=f"`{paypal}`", inline=False)

                        embed.set_thumbnail(url=interaction.user.display_avatar.url)

                        embed.set_author(name=interaction.guild.name, icon_url=interaction.guild.icon.url if interaction.guild.icon else None)

                        await interaction.response.send_message(embed=embed, ephemeral=True, view=WalletButtons())
            else:
                embed = discord.Embed(title="Access Denied", description="You do not have the necessary role to set a PayPal email.", color=discord.Color.from_str(embed_color))
                await interaction.response.send_message(embed=embed, ephemeral=True)
        
        else:
            if await self.check_admin_roles(interaction):
                async with aiosqlite.connect('database.db') as db:
                    async with db.execute(
                        "SELECT paypal FROM wallets WHERE member_id = ?", (member.id,)
                    ) as cursor:
                        row = await cursor.fetchone()

                paypal_email = row[0] if row else "Not Set"
                embed = discord.Embed(title=f"{member.name}'s PayPal Email", description=f"PayPal Email: {paypal_email}", color=discord.Color.from_str(embed_color))
                embed.set_thumbnail(url=member.display_avatar.url)
                await interaction.response.send_message(embed=embed, ephemeral=True)

            else:
                embed = discord.Embed(title="Access Denied", description="You do not have permission to view other people's PayPal email.", color=discord.Color.from_str(embed_color))
                await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(WalletCog(bot))