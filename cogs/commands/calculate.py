import discord
import yaml
from discord import app_commands
from discord.ext import commands

with open('config.yml', 'r') as file:
    data = yaml.safe_load(file)

embed_color = data["General"]["EMBED_COLOR"]
fee = data["Invoice"]["FEE"] / 100

class CalculateCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="calculate", description="Calculate the total needed to invoice")
    @app_commands.describe(amount="Target amount to calculate")
    async def calculate(self, interaction: discord.Interaction, amount: str) -> None:
        try:
            target_amount = float(amount)
            if target_amount <= 0:
                embed = discord.Embed(title="Error", description="Please provide a positive amount.", color=discord.Color.red())
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            amount_to_charge = target_amount / (1 - fee)

            amount_received = target_amount * (1 - fee)

            embed = discord.Embed(title="Invoice Calculation", description=f"Fee: {fee * 100:.2f}%", color=discord.Color.from_str(embed_color))
            embed.add_field(name="Target Amount", value=f"${target_amount:.2f}", inline=False)
            embed.add_field(name=f"Amount To Charge To Receive ${target_amount:.2f}", value=f"${amount_to_charge:.2f}", inline=False)
            embed.add_field(name=f"Amount Received If Charging ${target_amount:.2f}", value=f"${amount_received:.2f}", inline=False)

        except ValueError:
            embed = discord.Embed(title="Error", description="Invalid amount provided. Please enter a valid number.", color=discord.Color.red())
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(CalculateCog(bot))