import discord
import yaml
from discord.ext import commands
from datetime import datetime

with open('config.yml', 'r') as file:
    data = yaml.safe_load(file)

guild_id = data["General"]["GUILD_ID"]
embed_color = data["General"]["EMBED_COLOR"]
roles = data["Join"]["ROLES"]
welcome_channel_id = data["Join"]["WELCOME_CHANNEL_ID"]

class MemberEventsCog(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return

        guild = self.bot.get_guild(guild_id)
        welcome_channel = guild.get_channel(welcome_channel_id)
        
        for role in roles:
            try:
                role = guild.get_role(int(role))
                await member.add_roles(role)
            except:
                continue
        
        embed = discord.Embed(title="Welcome to Orchard Studios", description=f"Welcome {member.mention}, to **Orchard Studios** - Expert Freelancers for Rookie Pricing\n\nBe sure to check out our Pricing & Read through our Rules/TOS!", color=discord.Color.from_str(embed_color))
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="Orchard Studios | Open a Ticket for a Quote!")
        embed.timestamp = datetime.now()
        
        await welcome_channel.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(MemberEventsCog(bot))