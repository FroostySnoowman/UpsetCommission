import discord
import paypalrestsdk
import chat_exporter
import aiosqlite
import yaml
import io
from paypalrestsdk import Invoice
from datetime import datetime

with open('config.yml', 'r') as file:
    data = yaml.safe_load(file)

embed_color = data["General"]["EMBED_COLOR"]
name = data["Invoice"]["NAME"]
website = data["Invoice"]["WEBSITE"]
logo_url = data["Invoice"]["LOGO_URL"]
fee = data["Invoice"]["FEE"]

async def create_invoice(auth: paypalrestsdk.Api, total: int, department: str, freelancer: discord.Member, channel: discord.TextChannel, email: str = None):
    invoice_data = {
        "merchant_info": {
            "business_name": name,
            "website": website,
            "logo_url": logo_url
        },
        "items": [
            {
                "name": f"{department} Package",
                "description": f"Included in the package:\n1x {department} Package - Created by {freelancer.name}",
                "quantity": 1,
                "unit_price": {
                    "currency": "USD",
                    "value": total
                }
            }
        ],
        "note": "Thank you for supporting us :)",
        "payment_term": {
            "term_type": "NET_45"
        },
        "reference": f"{channel.name}",
        "allow_tip": True
    }

    if fee > 0:
        invoice_data["items"].append({
            "name": "Fee",
            "description": "The fee for this invoice as per our TOS.",
            "quantity": 1,
            "unit_price": {
                "currency": "USD",
                "value": total * (fee * 0.01)
            }
        })

    if email:
        invoice_data["billing_info"] = [{"email": email}]

    invoice = Invoice(invoice_data, api=auth)

    if invoice.create():
        invoice = Invoice.find(invoice['id'], api=auth)

        if invoice.send():
            return invoice.id
        else:
            return False

async def close_ticket(interaction: discord.Interaction):
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

    file_bytes = io.BytesIO(transcript.encode())
    file_name = f"{interaction.channel.name}.html"

    archive_channel_id = data["Tickets"].get("ARCHIVE_CHANNEL_ID")
    archive_channel = interaction.guild.get_channel(archive_channel_id) if archive_channel_id else None

    embed = discord.Embed(title="📜 Ticket Transcript 📜", description=f"Creator: {creator.mention}\nClosed At: <t:{timestamp}:f>\nChannel: {interaction.channel.name}", color=discord.Color.from_str(embed_color))
    embed.set_footer(text="Download the file above and open it to view the transcript")
    embed.timestamp = datetime.now()

    if archive_channel:
        archive_file = discord.File(io.BytesIO(transcript.encode()), filename=file_name)
        await archive_channel.send(embed=embed, file=archive_file)

    try:
        file_bytes.seek(0)
        user_file = discord.File(file_bytes, filename=file_name)
        await creator.send(embed=embed, file=user_file)
    except discord.Forbidden:
        pass

    async with aiosqlite.connect("database.db") as db:
        cursor = await db.execute("SELECT * FROM commissions WHERE channel_id = ?", (interaction.channel.id,))
        commission_data = await cursor.fetchone()

        if commission_data:
            try:
                freelancer_channel = interaction.guild.get_channel(commission_data[2])
                freelancer_message = await freelancer_channel.fetch_message(commission_data[3])
                await freelancer_message.delete()
            except:
                pass

            if commission_data[5] and commission_data[6] >= 0:
                cursor = await db.execute("SELECT * FROM wallets WHERE member_id = ?", (commission_data[5],))
                wallet_data = await cursor.fetchone()

                if wallet_data:
                    await db.execute('UPDATE wallets SET amount = amount + ? WHERE member_id = ?', (commission_data[6], commission_data[5]))
                
                try:
                    freelancer = interaction.guild.get_member(commission_data[5])
                    embed = discord.Embed(title="Payment Received", description=f"You have just received `${commission_data[6]:.2f}` to your balance. This payment is coming from the `{interaction.channel.name}` ticket. To withdraw this money, use the `/wallet` command. \n\n**Total Available For Withdrawal**\n`${wallet_data[3] + commission_data[6]:.2f}`", color=discord.Color.from_str(embed_color))
                    await freelancer.send(embed=embed)
                except:
                    pass
        
        await db.execute("DELETE FROM commissions WHERE channel_id = ?", (interaction.channel.id,))
        await db.execute("DELETE FROM questions WHERE channel_id = ?", (interaction.channel.id,))
        await db.execute("DELETE FROM quotes WHERE channel_id = ?", (interaction.channel.id,))
        await db.execute("DELETE FROM invoices WHERE channel_id = ?", (interaction.channel.id,))

        await db.commit()
    
    await interaction.channel.delete()