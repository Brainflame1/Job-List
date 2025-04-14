from dotenv import load_dotenv
load_dotenv()
import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
from datetime import datetime, timedelta, timezone

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --- Job Data Structure ---
class Job:
    def __init__(self, title, length, budget, deadline, description, author, duration_days):
        self.title = title
        self.length = length
        self.budget = budget
        self.deadline = deadline
        self.description = description
        self.style = "🎨 Not selected"
        self.claimed = False
        self.claimed_by = None
        self.author = author
        self.posted_at = datetime.now(timezone.utc)
        self.expires_at = self.posted_at + timedelta(days=duration_days)

jobs = []

# --- Role Matching ---
style_to_role = {
    "Documentary": "documentary editor",
    "Gaming": "gaming editor",
    "Commentary": "commentary editor",
    "Vlog": "vlog editor",
    "Shortform": "shortform editor",
    "Business Advice": "business editor",
    "Tutorial": "tutorial editor",
}

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
            discord.SelectOption(label="Tutorial", emoji="📚"),
        ]

        super().__init__(placeholder="🎯 Choose editing style...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.original_interaction.user:
            await interaction.response.send_message("🚫 Only the user who posted this job can select the style.", ephemeral=True)
            return

        style = self.values[0]
        self.job.style = style
        self.embed.add_field(name="🎨 Editing Style", value=style, inline=False)

        view = JobView(self.job)
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
            await interaction.response.send_message("🚫 This job has already been claimed.", ephemeral=True)
            return

        required_role_name = style_to_role.get(self.job.style)
        if required_role_name:
            required_role = discord.utils.get(interaction.guild.roles, name=required_role_name)
            if required_role and required_role not in interaction.user.roles:
                await interaction.response.send_message(f"🚫 You need the **{required_role_name}** role to claim this job.", ephemeral=True)
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
        check_expired_jobs.start()
    except Exception as e:
        print(f"❌ Slash command sync failed: {e}")

# --- Slash Command: Post Job ---
@bot.tree.command(name="job", description="➕ Post a new job listing")
@app_commands.describe(
    title="Job title (e.g. YouTube Vlog: Trip to Japan)",
    length="Length of the video or content (e.g. 10-12 minutes)",
    budget="Payment offered (e.g. $200)",
    deadline="When it’s due (e.g. 2025-04-25)",
    description="Any extra info the editor should know (e.g. add subtitles, transitions)",
    duration_days="How long the job stays active (in days, e.g. 5)"
)
async def job(
    interaction: discord.Interaction,
    title: str,
    length: str,
    budget: str,
    deadline: str,
    description: str,
    duration_days: int = 7
):
    embed = discord.Embed(title="📝 New Job Posted", color=0x00ff99)
    embed.add_field(name="📌 Title", value=title, inline=False)
    embed.add_field(name="⏳ Length", value=length, inline=False)
    embed.add_field(name="💰 Budget", value=budget, inline=False)
    embed.add_field(name="📅 Deadline", value=deadline, inline=False)
    embed.add_field(name="📝 Description", value=description, inline=False)
    embed.add_field(name="🕓 Expires On", value=(datetime.now(timezone.utc) + timedelta(days=duration_days)).strftime("%Y-%m-%d"), inline=False)

    job_obj = Job(title, length, budget, deadline, description, interaction.user, duration_days)
    jobs.append(job_obj)

    view = StyleDropdownView(embed, interaction, job_obj)
    await interaction.response.send_message(embed=embed, view=view)

# --- Slash Command: List Jobs ---
@bot.tree.command(name="jobs", description="📋 Show the list of active job listings")
async def list_jobs(interaction: discord.Interaction):
    active_jobs = [job for job in jobs if not job.claimed and job.expires_at > datetime.now(timezone.utc)]
    if not active_jobs:
        await interaction.response.send_message("📭 There are no active jobs at the moment.", ephemeral=True)
        return

    embed = discord.Embed(title="🗂️ Active Job Listings", color=0x00ffcc)

    for job in active_jobs:
        embed.add_field(
            name=f"📌 {job.title}",
            value=f"**Length:** {job.length}\n"
                  f"**Budget:** {job.budget}\n"
                  f"**Deadline:** {job.deadline}\n"
                  f"**Style:** {job.style}\n"
                  f"**Description:** {job.description}\n"
                  f"**Posted by:** {job.author.mention}\n"
                  f"**Expires:** {job.expires_at.strftime('%Y-%m-%d')}",
            inline=False
        )

    await interaction.response.send_message(embed=embed)

# --- Background Task: Expiry Check ---
@tasks.loop(minutes=1)
async def check_expired_jobs():
    now = datetime.now(timezone.utc)
    expired = [job for job in jobs if not job.claimed and job.expires_at <= now]
    for job in expired:
        jobs.remove(job)

bot.run(os.getenv("DISCORD_TOKEN"))
