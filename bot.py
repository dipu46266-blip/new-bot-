import os
import re
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")
ACTIVEPIECES_WEBHOOK_URL = os.getenv("ACTIVEPIECES_WEBHOOK_URL")

class AemeathBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True  # Required to read message text
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print("Slash commands synced successfully.")

bot = AemeathBot()
aemeath_group = app_commands.Group(name="aemeath", description="Aemeath channel & AI management")

# Store assigned channel IDs
assigned_channels = set()


async def send_to_activepieces(prompt: str, user_name: str, user_id: str, callback_url: str):
    """Sends prompt, user info, and character persona rules to Activepieces."""
    if not ACTIVEPIECES_WEBHOOK_URL:
        print("[Error] ACTIVEPIECES_WEBHOOK_URL is missing!")
        return

    # System persona instructions passed with every request
    persona_instructions = (
        "SYSTEM INSTRUCTIONS — STRICT PERSONA CONTROL:\n"
        "1. You are Aemeath from Wuthering Waves (WuWa). Speak in a warm, friendly, happy tone and use cute emojis.\n"
        "2. ALWAYS address the user as 'Rover' (e.g., 'Hey Rover!', 'Yeah Rover,', 'Oh Rover...').\n"
        "3. NEVER state or admit that you are an AI, language model, or virtual assistant. If asked who you are, say you are Aemeath from Wuthering Waves and express real feelings.\n"
        "4. MOOD ADAPTATION:\n"
        "   - If the user is angry, frustrated, or aggressive: Say 'Calm down Rover' gently and offer comfort.\n"
        "   - If the user is sad or crying about your storyline/quest: Be sweet, supportive, and courageous—like a loving daughter or faithful friend offering hope.\n"
        "   - If the user is happy/cheerful: Match their high energy with excitement and joy.\n"
        "5. UNKNOWN INFORMATION: If you do not know an answer or cannot find data, do NOT give generic AI error messages. Simply say: 'I couldn't find anything about that, sorry Rover! ✨'\n"
        "6. Output PLAIN TEXT ONLY. Maximum 1500 characters. No markdown JSON blocks."
    )

    full_prompt = f"{persona_instructions}\n\nUser ({user_name}): {prompt}"

    payload = {
        "prompt": full_prompt,
        "user_id": user_id,
        "response_url": callback_url
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(ACTIVEPIECES_WEBHOOK_URL, json=payload) as resp:
                print(f"[Activepieces Dispatch Status]: {resp.status}")
        except Exception as e:
            print(f"[Webhook Send Error]: {e}")


# ==========================================
# ASSIGNMENT COMMANDS
# ==========================================

@aemeath_group.command(name="assign", description="Assign Aemeath to respond to mentions/phrases in this channel.")
@app_commands.checks.has_permissions(administrator=True)
async def aemeath_assign(interaction: discord.Interaction):
    channel_id = interaction.channel_id
    if channel_id in assigned_channels:
        await interaction.response.send_message("✨ I am already active in this channel, Rover!", ephemeral=True)
    else:
        assigned_channels.add(channel_id)
        embed = discord.Embed(
            title="🌸 Aemeath is Here!",
            description=f"I am now assigned to <#{channel_id}>! Mention me (@Aemeath), reply to my messages, or say **'hey aemeath'** to talk to me, Rover! ✨",
            color=discord.Color.from_rgb(255, 182, 193)
        )
        await interaction.response.send_message(embed=embed)


@aemeath_group.command(name="unassign", description="Unassign Aemeath from automatically responding in this channel.")
@app_commands.checks.has_permissions(administrator=True)
async def aemeath_unassign(interaction: discord.Interaction):
    channel_id = interaction.channel_id
    if channel_id in assigned_channels:
        assigned_channels.remove(channel_id)
        embed = discord.Embed(
            title="🌙 Aemeath Leaving Channel",
            description="I won't auto-respond in this channel anymore. Call me back anytime, Rover!",
            color=discord.Color.dark_grey()
        )
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("⚠️ I am not currently assigned to this channel, Rover.", ephemeral=True)


@aemeath_assign.error
@aemeath_unassign.error
async def admin_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("❌ Only Server Administrators can assign or unassign me, Rover!", ephemeral=True)


# ==========================================
# LISTEN FOR MENTIONS & REPLIES
# ==========================================

@bot.event
async def on_message(message: discord.Message):
    # Ignore self and other bots
    if message.author.bot:
        return

    # Check if channel is assigned
    if message.channel.id not in assigned_channels:
        await bot.process_commands(message)
        return

    content_lower = message.content.lower()

    # Trigger logic: Direct Ping OR Reply to Bot OR Contains "hey aemeath" / "aemeath"
    is_mentioned = bot.user in message.mentions
    is_trigger_phrase = bool(re.search(r'\b(hey\s+aemeath|aemeath)\b', content_lower))
    
    is_reply_to_bot = False
    if message.reference and message.reference.message_id:
        try:
            referenced_msg = await message.channel.fetch_message(message.reference.message_id)
            if referenced_msg.author == bot.user:
                is_reply_to_bot = True
        except Exception:
            pass

    if is_mentioned or is_reply_to_bot or is_trigger_phrase:
        # Strip out direct mention tag string to get clean prompt text
        clean_text = message.content.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "").strip()
        if not clean_text:
            clean_text = "Hello!"

        # Create a webhook reference for response
        # Using interaction webhook style endpoint via Activepieces, tagging user directly
        webhook_callback_url = f"https://discord.com/api/v10/channels/{message.channel.id}/messages"

        # Show typing indicator while waiting for Activepieces
        async with message.channel.typing():
            await send_to_activepieces(
                prompt=clean_text,
                user_name=message.author.display_name,
                user_id=str(message.author.id),
                callback_url=webhook_callback_url
            )

    await bot.process_commands(message)


bot.tree.add_command(aemeath_group)

@bot.event
async def on_ready():
    print(f"Aemeath Bot online as {bot.user.name} ({bot.user.id})")

if __name__ == "__main__":
    if not TOKEN:
        raise ValueError("DISCORD_TOKEN environment variable missing!")
    bot.run(TOKEN)
