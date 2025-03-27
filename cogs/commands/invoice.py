import discord
import paypalrestsdk
import aiosqlite
import asyncio
import yaml
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime
from typing import Optional
from cogs.functions.utils import create_invoice

with open('config.yml', 'r') as file:
    data = yaml.safe_load(file)

guild_id = data["General"]["GUILD_ID"]
embed_color = data["General"]["EMBED_COLOR"]
paypal_client_id = data["Invoice"]["PAYPAL_CLIENT_ID"]
paypal_client_secret = data["Invoice"]["PAYPAL_CLIENT_SECRET"]
invoice_roles = data["Permissions"].get("INVOICE_ROLES", [])
commissions = data["Commissions"]

my_api = paypalrestsdk.Api(
    {
        'mode': 'live',
        'client_id': paypal_client_id,
        'client_secret': paypal_client_secret
    }
)

class PayPalLink(discord.ui.View):
    def __init__(self, id):
        super().__init__()
        self.add_item(discord.ui.Button(emoji='<:paypal:1339028680537804901>', label='Pay', url=f'https://www.paypal.com/invoice/p/#{id}'))

class InvoiceCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def cog_load(self):
        self.paypal_loop.start()

    @tasks.loop(seconds = 10)
    async def paypal_loop(self):
        async with aiosqlite.connect('database.db') as db:
            cursor = await db.execute('SELECT * FROM invoices')
            invoices = await cursor.fetchall()

            for invoice in invoices:
                try:
                    channel = self.bot.get_channel(invoice[0])

                    partialmessage = channel.get_partial_message(invoice[1])

                    message = await channel.fetch_message(partialmessage.id)

                    payment = paypalrestsdk.Invoice.find(f"{invoice[2]}", api=my_api)

                    status = payment['status']
                    status = "PAID"

                    if status == "PAID" or status == "MARKED_AS_PAID":
                        await db.execute('UPDATE commissions SET amount = amount + ? WHERE channel_id = ?', (invoice[3], invoice[0]))
                        await db.execute('DELETE FROM invoices WHERE message_id=?', (invoice[1],))

                        embed = discord.Embed(title="Invoice - Paid", description="✔ - Thank you for making the Payment! We can now begin the commission!", colour=discord.Color.from_str(embed_color))
                        embed.add_field(name="Amount Paid", value=f"${invoice[3]}", inline=True)
                        embed.add_field(name="Invoice ID", value=f"{invoice[2]}", inline=True)
                        embed.set_thumbnail(url="https://media.discordapp.net/attachments/964703100839555092/1339635097418207296/Eo_circle_orange_checkmark.svg.png?ex=67af6fe8&is=67ae1e68&hm=405de4ac3529d8f925950208292b2d530bcf1084577966cb27aebbc2c32b37ab&=&format=webp&quality=lossless&width=532&height=532")
                        embed.set_footer(text="Orchard Studios")
                        embed.timestamp = datetime.now()
                        
                        msg = await message.edit(embed=embed, attachments=message.attachments)

                        embed = discord.Embed(title="Invoice Payment Successful", description=f"Successfully received the paypal for this [invoice]({msg.jump_url}) (**${invoice[3]}**).", color=discord.Color.from_str(embed_color))
                        await channel.send(embed=embed)
                    else:
                        continue
                except:
                    await db.execute('DELETE FROM invoices WHERE message_id=?', (invoice[1],))
            
            await db.commit()

    @paypal_loop.before_loop
    async def before_paypal_loop(self):
        await self.bot.wait_until_ready()

    async def check_permissions(self, interaction: discord.Interaction) -> bool:
        user_roles = [role.id for role in interaction.user.roles]

        return any(role in user_roles for role in invoice_roles)

    @app_commands.command(name="invoice", description="Generates a PayPal invoice")
    @app_commands.describe(amount="The amount of the invoice", email="The email of the user")
    async def invoice(self, interaction: discord.Interaction, amount: int, email: Optional[str]) -> None:
        if not await self.check_permissions(interaction):
            embed = discord.Embed(title="No Permission", description="You do not have permission to use this command.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        await interaction.response.defer(thinking=True)

        async with aiosqlite.connect("database.db") as db:
            cursor = await db.execute("SELECT * FROM commissions WHERE channel_id = ?", (interaction.channel.id,))
            commission_data = await cursor.fetchone()
            
            if not commission_data:
                embed = discord.Embed(title="Error", description="This command can only be used in a commission channel.", color=discord.Color.red())
                await interaction.followup.send(embed=embed)
                return
            
            if not commission_data[5]:
                embed = discord.Embed(title="Error", description="This commission has no freelancer!", color=discord.Color.red())
                await interaction.followup.send(embed=embed)
                return
            
            freelancer = interaction.guild.get_member(commission_data[5])
            if not freelancer:
                embed = discord.Embed(title="Error", description="The freelancer for this commission is not in the server.", color=discord.Color.red())
                await interaction.followup.send(embed=embed)
                return
            
            department = next((c["department"] for c in commissions if c["channel"] == commission_data[2]), None)
            if not department:
                embed = discord.Embed(title="Error", description="This command can only be used in a commission channel.", color=discord.Color.red())
                embed.set_footer(text="Failed to find department")
                await interaction.followup.send(embed=embed)
                return

            response = await create_invoice(my_api, amount, department, freelancer, interaction.channel, email)
            if not response:
                embed = discord.Embed(title="Error", description="An error occurred while creating the invoice.", color=discord.Color.from_str(embed_color))
                embed.set_footer(text="Deleting in 10 seconds")
                await interaction.followup.send(embed=embed)
                msg = await interaction.original_response()
                await asyncio.sleep(10)
                await msg.delete()
                return
            
            async with aiosqlite.connect('database.db') as db:
                embed = discord.Embed(title="**Invoice - Unpaid **", description="⌛ - Invoice has yet to be paid \n\nPlease remember all LIVE work requires 100% of the payment upfront.", colour=discord.Color.from_str(embed_color))
                embed.add_field(name="Amount Due", value=f"${amount}", inline=True)
                embed.add_field(name="Invoice ID", value=f"{response}", inline=True)
                embed.set_thumbnail(url="https://media.discordapp.net/attachments/964703100839555092/1339634022791516272/8531200.png?ex=67af6ee8&is=67ae1d68&hm=c21f546117e5245f31577ef6d00dd25d88a6980ec8a2ddc423c424ed4996d6b1&=&format=webp&quality=lossless")
                embed.set_footer(text="Orchard Studios")
                embed.timestamp = datetime.now()

                await interaction.followup.send(embed=embed, view=PayPalLink(response))
                msg = await interaction.original_response()

                await db.execute('INSERT INTO invoices VALUES (?,?,?,?);', (interaction.channel.id, msg.id, response, amount))
                await db.commit()

async def setup(bot: commands.Bot):
    await bot.add_cog(InvoiceCog(bot))