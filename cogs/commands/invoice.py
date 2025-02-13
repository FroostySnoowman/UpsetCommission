import discord
import paypalrestsdk
import aiosqlite
import asyncio
import qrcode
import yaml
import io
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

            guild = self.bot.get_guild(guild_id)

            for invoice in invoices:
                channel = self.bot.get_channel(invoice[0])

                partialmessage = channel.get_partial_message(invoice[1])

                message = await channel.fetch_message(partialmessage.id)

                payment = paypalrestsdk.Invoice.find(f"{invoice[2]}", api=my_api)

                status = payment['status']

                if status == "PAID" or status == "MARKED_AS_PAID":
                    await db.execute('DELETE FROM invoices WHERE message_id=?', (invoice[1],))

                    embed = discord.Embed(title="Invoice Paid", description=f"Payment confirmed! This invoice has been paid. This order may continue.", color=discord.Color.from_str(embed_color))
                    embed.set_thumbnail(url=message.embeds[0].thumbnail.url)
                    embed.add_field(name="Paid", value=f"${invoice[3]}", inline=True)
                    embed.add_field(name="Invoice ID", value=f"{invoice[2]}", inline=True)
                    embed.add_field(name="Link", value=f"[View Invoice](https://www.paypal.com/invoice/p/#{invoice[2]})", inline=True)
                    embed.set_footer(text=f"{guild.name}")
                    embed.timestamp = datetime.now()
                    
                    msg = await message.edit(embed=embed, attachments=message.attachments)

                    embed = discord.Embed(title="Invoice Payment Successful", description=f"Successfully received the paypal for this [invoice]({msg.jump_url}) (**${invoice[3]}**).", color=discord.Color.from_str(embed_color))
                    await channel.send(embed=embed)
                else:
                    continue
            
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

        response = await create_invoice(my_api, amount, email)
        if not response:
            embed = discord.Embed(title="Error", description="An error occurred while creating the invoice.", color=discord.Color.from_str(embed_color))
            embed.set_footer(text="Deleting in 10 seconds")
            await interaction.followup.send(embed=embed)
            msg = await interaction.original_response()
            await asyncio.sleep(10)
            await msg.delete()
            return
        
        async with aiosqlite.connect('database.db') as db:
            img = qrcode.make(f'https://www.paypal.com/invoice/p/#{response}')
            fp = io.BytesIO()
            img.save(fp)
            fp.seek(0)
            f = discord.File(fp, filename="paypal.png")

            embed = discord.Embed(title="Invoice Pending", description=f"Payment pending!", color=discord.Color.from_str(embed_color))
            embed.set_thumbnail(url="attachment://paypal.png")
            embed.add_field(name="Invoice Price", value=f"${amount}", inline=True)
            embed.add_field(name="Invoice ID", value=f"{response}", inline=True)
            embed.add_field(name="Link", value=f"[View Invoice](https://www.paypal.com/invoice/p/#{response})", inline=True)
            embed.set_footer(text=f"{interaction.guild.name}")
            embed.timestamp = datetime.now()

            await interaction.followup.send(embed=embed, view=PayPalLink(response), files=[f])
            msg = await interaction.original_response()

            await db.execute('INSERT INTO invoices VALUES (?,?,?,?);', (interaction.channel.id, msg.id, response, amount))
            await db.commit()

async def setup(bot: commands.Bot):
    await bot.add_cog(InvoiceCog(bot))