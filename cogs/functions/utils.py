import discord
import paypalrestsdk
import chat_exporter
import htmlmin
import yaml
import io
from paypalrestsdk import Invoice
from datetime import datetime

with open('config.yml', 'r') as file:
    data = yaml.safe_load(file)

embed_color = data["General"]["EMBED_COLOR"]
name = data["Invoice"]["NAME"]
website = data["Invoice"]["WEBSITE"]
tos = data["Invoice"]["TOS"]
fee = data["Invoice"]["FEE"]

async def create_invoice(auth: paypalrestsdk.Api, total: int, email: str = None):
    invoice_data = {
        "merchant_info": {
            "business_name": name,
            "website": website
        },
        "items": [
            {
                "name": "Service",
                "description": f"Service at {name}",
                "quantity": 1,
                "unit_price": {
                    "currency": "USD",
                    "value": total
                }
            }
        ],
        "note": f"This invoice is for your ticket at {name}.",
        "terms": tos,
        "payment_term": {
            "term_type": "NET_45"
        }
    }

    if fee > 0:
        invoice_data["items"].append({
            "name": "Fee",
            "description": "The fee for this invoice as per our TOS.",
            "quantity": 1,
            "unit_price": {
                "currency": "USD",
                "value": fee
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