import discord
from discord import app_commands
from discord.ext import commands
import os
from dotenv import load_dotenv  # Import dotenv to load environment variables

# Load environment variables from .env file
load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --- Job Data Structure ---
class Job:
    def __init__(self, title, length, budget, deadline, description, style="Not yet selected"):
        self.title = title
        self.length = length
        self.budget = budget
        self.deadline = deadline
        self.description = description
        self.style = style
        self.claimed = False
        self.claimed_by = None

jobs = []  # List to hold active jobs

# --- UI Elements ---
class StyleSelect(discord.ui.Select):
    def __init__(self, embed, interaction, job):
        self.embed = embed
        self.original_interaction = interaction
        self.job = job

        options = [
            discord.SelectOption(label="Documentary", emoji="🎬"),
            discord.SelectOption(label="Gaming", emoji="🎮"),
            discord.SelectOption(label="Commentary", emoji="🎙️"),
            discord.SelectOption(label="Vlog", emoji="📹"),
            discord.SelectOption(label="Shortform", emoji="📱"),
            discord.SelectOption(label="Business Advice", emoji="💼"),
        ]

        super().__init__(placeholder="Choose editing style...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        style = self.values[0]
        self.job.style = style
        self.embed.add_field(name="Editing Style", value=style, inline=False)

        view = JobView(self.job)  # Pass the job object to update the claim button state
        await interaction.response.edit_message(embed=self.embed, view=view)

class StyleDropdownView(discord.ui.View):
    def __init__(self, embed, interaction, job):
        super().__init__(timeout=60)
        self.add_item(StyleSelect(embed, interaction, job))

class JobView(discord.ui.View):
    def __init__(self, job):
        super().__init__(timeout=None)
        self.job = job

    @discord.ui.button(label="✅ Claim Job", style=discord.ButtonStyle.success, custom_id="claim_button")
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.job.claimed:
            await interaction.response.send_message("This job has already been claimed.", ephemeral=True)
            return

        # Check if the user has the correct role for the editing style
        role_needed = None
        for role in interaction.user.roles:
            if role.name.lower() == f"{self.job.style.lower()} editor":
                role_needed = role
                break

        if not role_needed:
            await interaction.response.send_message(f"You need the `{self.job.style} Editor` role to claim this job.", ephemeral=True)
            return

        self.job.claimed = True
        self.job.claimed_by = interaction.user
        await interaction.response.send_message(f"{interaction.user.mention} has claimed this job! 🔒", ephemeral=False)
        button.disabled = True
        await interaction.message.edit(view=self)

# --- Bot Setup ---
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"❌ Slash command sync failed: {e}")

# Command to show active jobs
@bot.tree.command(name="jobs", description="Show the list of active job listings")
async def jobs(interaction: discord.Interaction):
    if not jobs:
        await interaction.response.send_message("There are no active jobs at the moment.", ephemeral=True)
        return
    
    embed = discord.Embed(title="📝 Active Job Listings", color=0x00ff99)
    
    for idx, job in enumerate(jobs):
        status = "Claimed by " + job.claimed_by.mention if job.claimed else "Available"
        embed.add_field(
            name=f"{job.title} ({status})", 
            value=f"Length: {job.length}\nBudget: {job.budget}\nDeadline: {job.deadline}\nStyle: {job.style}\nDescription: {job.description}",
            inline=False
        )

    await interaction.response.send_message(embed=embed)

# Command to post a new job
@bot.tree.command(name="job", description="Post a new job listing")
@app_commands.describe(
    title="Job title",
    length="Length of the video or content",
    budget="Payment offered",
    deadline="When it’s due",
    description="Any extra info the editor should know"
)
async def job(
    interaction: discord.Interaction,
    title: str,
    length: str,
    budget: str,
    deadline: str,
    description: str
):
    embed = discord.Embed(title="📝 New Job Posted", color=0x00ff99)
    embed.add_field(name="Title", value=title, inline=False)
    embed.add_field(name="Length", value=length, inline=False)
    embed.add_field(name="Budget", value=budget, inline=False)
    embed.add_field(name="Deadline", value=deadline, inline=False)
    embed.add_field(name="Description", value=description, inline=False)

    job = Job(title, length, budget, deadline, description)
    jobs.append(job)

    view = StyleDropdownView(embed, interaction, job)
    await interaction.response.send_message(embed=embed, view=view)

# Run the bot using the token from the .env file
bot.run(os.getenv("DISCORD_TOKEN"))
