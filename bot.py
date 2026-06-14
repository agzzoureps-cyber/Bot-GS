import discord
from discord.ext import commands
import asyncio
import datetime
import os
import re
from collections import defaultdict

TOKEN = os.environ.get("DISCORD_TOKEN")
PREFIX = "+"
MUTE_ROLE_NAME = "Muted"
LOG_CHANNEL_NAME = "mod-logs"

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

snipe_data = {}
edit_snipe = {}
warnings = defaultdict(list)
afk_users = {}

@bot.event
async def on_message_delete(message):
    if message.author.bot:
        return
    snipe_data[message.channel.id] = {
        "content": message.content or "[Aucun texte]",
        "author": str(message.author),
        "avatar": str(message.author.display_avatar.url),
        "timestamp": datetime.datetime.utcnow()
    }

@bot.event
async def on_message_edit(before, after):
    if before.author.bot or before.content == after.content:
        return
    edit_snipe[before.channel.id] = {
        "before": before.content or "[Aucun texte]",
        "after": after.content or "[Aucun texte]",
        "author": str(before.author),
        "avatar": str(before.author.display_avatar.url),
        "timestamp": datetime.datetime.utcnow()
    }

NUMBER_EMOJIS = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣"]
VOTE_CHANNEL_ID = 1515420912286175242

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if message.channel.id == VOTE_CHANNEL_ID:
        for emoji in NUMBER_EMOJIS:
            await message.add_reaction(emoji)
    if message.author.id in afk_users:
        reason = afk_users.pop(message.author.id)
        await message.channel.send(f"👋 Bienvenue {message.author.mention} ! Tu n'es plus AFK (tu l'étais : *{reason}*).", delete_after=8)
    for user in message.mentions:
        if user.id in afk_users:
            await message.channel.send(f"💤 **{user.display_name}** est AFK : *{afk_users[user.id]}*", delete_after=8)
    await bot.process_commands(message)

@bot.command(name="help")
async def help_cmd(ctx, category: str = None):
    categories = {
        "mod": {"emoji": "🔨", "title": "Modération", "cmds": [("+ban [user] [raison]","Bannit"),("+unban [user#0000]","Débannit"),("+kick [user] [raison]","Expulse"),("+mute [user] [durée] [raison]","Mute"),("+unmute [user]","Démute"),("+warn [user] [raison]","Avertit"),("+warns [user]","Liste warnings"),("+clearwarns [user]","Efface warnings"),("+softban [user]","Ban+unban"),("+massban [@u1 @u2]","Ban massif")]},
        "channel": {"emoji": "📢", "title": "Canaux", "cmds": [("+clear [n]","Supprime n messages"),("+purgeuser [user]","Purge msgs d'un user"),("+lock","Verrouille"),("+unlock","Déverrouille"),("+slowmode [s]","Slowmode"),("+nuke","Recrée le salon"),("+hide","Cache"),("+unhide","Révèle"),("+renamechannel [nom]","Renomme le salon")]},
        "info": {"emoji": "ℹ️", "title": "Informations", "cmds": [("+userinfo [user]","Infos utilisateur"),("+serverinfo","Infos serveur"),("+avatar [user]","Avatar"),("+roleinfo [role]","Infos rôle"),("+snipe","Dernier msg supprimé"),("+editsnipe","Dernier msg édité"),("+botinfo","Infos bot")]},
        "util": {"emoji": "🛠️", "title": "Utilitaires", "cmds": [("+embed Titre | Desc","Crée un embed"),("+say [message]","Bot répète"),("+afk [raison]","Mode AFK"),("+poll [question]","Sondage"),("+timer [s]","Timer"),("+ping","Latence"),("+addrole [user] [role]","Ajoute rôle"),("+removerole [user] [role]","Retire rôle"),("+rename [user] [pseudo]","Change le pseudo"),("+announce [msg]","Annonce"),("+ticket","Panel tickets")]}
    }
    if category and category.lower() in categories:
        c = categories[category.lower()]
        e = discord.Embed(title=f"{c['emoji']} Commandes – {c['title']}", color=0xFFFFFF)
        for cmd, desc in c["cmds"]:
            e.add_field(name=f"`{cmd}`", value=desc, inline=False)
        e.set_footer(text=f"Préfixe : {PREFIX}")
        return await ctx.send(embed=e)
    e = discord.Embed(title="📖 Aide – Bot Modération", description="Utilise `+help [catégorie]`\n\n**Catégories :**", color=0xFFFFFF, timestamp=datetime.datetime.utcnow())
    for key, c in categories.items():
        e.add_field(name=f"{c['emoji']} `+help {key}`", value=c["title"], inline=True)
    e.set_thumbnail(url=bot.user.display_avatar.url)
    e.set_footer(text=f"Bot lancé par {ctx.author}", icon_url=ctx.author.display_avatar.url)
    await ctx.send(embed=e)

async def get_or_create_mute_role(guild):
    role = discord.utils.get(guild.roles, name=MUTE_ROLE_NAME)
    if not role:
        role = await guild.create_role(name=MUTE_ROLE_NAME, reason="Création du rôle Muted")
        for channel in guild.channels:
            try:
                await channel.set_permissions(role, send_messages=False, speak=False, add_reactions=False)
            except Exception:
                pass
    return role

async def log_action(guild, embed):
    ch = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
    if ch:
        try:
            await ch.send(embed=embed)
        except Exception:
            pass

def mod_embed(title, description, color=0xFFFFFF, **fields):
    e = discord.Embed(title=title, description=description, color=color, timestamp=datetime.datetime.utcnow())
    for k, v in fields.items():
        e.add_field(name=k, value=v, inline=True)
    return e

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="Aucune raison fournie"):
    await member.ban(reason=reason)
    e = mod_embed("🔨 Banni", f"**{member}** a été banni.", Raison=reason, Modérateur=str(ctx.author))
    await ctx.send(embed=e)
    await log_action(ctx.guild, e)

@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, *, user_tag: str):
    bans = [entry async for entry in ctx.guild.bans()]
    for entry in bans:
        if str(entry.user) == user_tag:
            await ctx.guild.unban(entry.user)
            e = mod_embed("✅ Débanni", f"**{entry.user}** a été débanni.", Modérateur=str(ctx.author))
            return await ctx.send(embed=e)
    await ctx.send(f"❌ Utilisateur `{user_tag}` introuvable dans les bans.")

@bot.command()
@commands.has_permissions(ban_members=True)
async def softban(ctx, member: discord.Member, *, reason="Aucune raison fournie"):
    await member.ban(reason=f"Softban: {reason}", delete_message_days=7)
    await ctx.guild.unban(member)
    e = mod_embed("🔨 Softban", f"**{member}** a été softban.", Raison=reason, Modérateur=str(ctx.author))
    await ctx.send(embed=e)
    await log_action(ctx.guild, e)

@bot.command()
@commands.has_permissions(ban_members=True)
async def massban(ctx, members: commands.Greedy[discord.Member], *, reason="Aucune raison fournie"):
    if not members:
        return await ctx.send("❌ Mentionne au moins un membre.")
    count = 0
    for m in members:
        try:
            await m.ban(reason=reason)
            count += 1
        except Exception:
            pass
    await ctx.send(embed=mod_embed("🔨 Massban", f"{count} membre(s) bannis.", Raison=reason, Modérateur=str(ctx.author)))

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="Aucune raison fournie"):
    await member.kick(reason=reason)
    e = mod_embed("👢 Expulsé", f"**{member}** a été expulsé.", Raison=reason, Modérateur=str(ctx.author))
    await ctx.send(embed=e)
    await log_action(ctx.guild, e)

def parse_duration(duration_str):
    match = re.fullmatch(r"(\d+)([smhd])", duration_str.lower())
    if not match:
        return None
    value, unit = int(match.group(1)), match.group(2)
    return value * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]

@bot.command()
@commands.has_permissions(manage_roles=True)
async def mute(ctx, member: discord.Member, duration: str = None, *, reason="Aucune raison fournie"):
    role = await get_or_create_mute_role(ctx.guild)
    await member.add_roles(role, reason=reason)
    dur_text = "Indéfinie"
    seconds = None
    if duration:
        seconds = parse_duration(duration)
        if seconds:
            dur_text = duration
        else:
            reason = f"{duration} {reason}".strip()
    e = mod_embed("🔇 Mute", f"**{member}** a été mute.", Raison=reason, Durée=dur_text, Modérateur=str(ctx.author))
    await ctx.send(embed=e)
    await log_action(ctx.guild, e)
    if seconds:
        await asyncio.sleep(seconds)
        if role in member.roles:
            await member.remove_roles(role, reason="Fin du mute automatique")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def unmute(ctx, member: discord.Member):
    role = await get_or_create_mute_role(ctx.guild)
    if role in member.roles:
        await member.remove_roles(role)
        e = mod_embed("🔊 Unmute", f"**{member}** a été unmute.", Modérateur=str(ctx.author))
        await ctx.send(embed=e)
        await log_action(ctx.guild, e)
    else:
        await ctx.send(f"❌ **{member}** n'est pas mute.")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason="Aucune raison fournie"):
    warnings[member.id].append({"raison": reason, "par": str(ctx.author), "date": str(datetime.date.today())})
    count = len(warnings[member.id])
    e = mod_embed("⚠️ Avertissement", f"**{member}** a reçu un avertissement. (Total : {count})", Raison=reason, Modérateur=str(ctx.author))
    await ctx.send(embed=e)
    try:
        await member.send(embed=mod_embed("⚠️ Tu as reçu un avertissement", f"Serveur : **{ctx.guild.name}**", Raison=reason, Modérateur=str(ctx.author)))
    except Exception:
        pass

@bot.command()
@commands.has_permissions(manage_messages=True)
async def warns(ctx, member: discord.Member):
    w = warnings.get(member.id, [])
    if not w:
        return await ctx.send(f"✅ **{member}** n'a aucun avertissement.")
    e = discord.Embed(title=f"⚠️ Avertissements de {member}", color=0xFFFFFF)
    for i, entry in enumerate(w, 1):
        e.add_field(name=f"#{i} – {entry['date']}", value=f"**Raison :** {entry['raison']}\n**Par :** {entry['par']}", inline=False)
    await ctx.send(embed=e)

@bot.command()
@commands.has_permissions(manage_messages=True)
async def clearwarns(ctx, member: discord.Member):
    warnings[member.id] = []
    await ctx.send(embed=mod_embed("✅ Warnings effacés", f"Les avertissements de **{member}** ont été supprimés."))

@bot.command()
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int):
    if amount < 1 or amount > 500:
        return await ctx.send("❌ Entre 1 et 500 messages.")
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"🗑️ {len(deleted)-1} message(s) supprimé(s).", delete_after=5)

@bot.command()
@commands.has_permissions(moderate_members=True)
async def to(ctx, member: discord.Member, duration: str = "10m", *, reason="Aucune raison fournie"):
    seconds = parse_duration(duration)
    if not seconds:
        return await ctx.send("❌ Durée invalide. Ex: `+to @user 10m raison`")
    until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=seconds)
    await member.timeout(until, reason=reason)
    e = mod_embed("🔇 Timeout", f"**{member}** a été mis en timeout.", Durée=duration, Raison=reason, Modérateur=str(ctx.author))
    await ctx.send(embed=e)
    await log_action(ctx.guild, e)

@bot.command()
@commands.has_permissions(moderate_members=True)
async def unto(ctx, member: discord.Member):
    await member.timeout(None)
    e = mod_embed("✅ Timeout retiré", f"**{member}** n'est plus en timeout.", Modérateur=str(ctx.author))
    await ctx.send(embed=e)

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purgeuser(ctx, member: discord.Member, amount: int = 50):
    deleted = await ctx.channel.purge(limit=200, check=lambda m: m.author == member)
    await ctx.send(f"🗑️ {len(deleted)} message(s) de **{member}** supprimé(s).", delete_after=5)

@bot.command()
@commands.has_permissions(manage_channels=True)
async def lock(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    await channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send(embed=mod_embed("🔒 Verrouillé", f"{channel.mention} est verrouillé."))

@bot.command()
@commands.has_permissions(manage_channels=True)
async def unlock(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    await channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send(embed=mod_embed("🔓 Déverrouillé", f"{channel.mention} est ouvert."))

@bot.command()
@commands.has_permissions(manage_channels=True)
async def slowmode(ctx, seconds: int):
    await ctx.channel.edit(slowmode_delay=seconds)
    await ctx.send(f"⏱️ Slowmode défini à **{seconds}s**.")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def nuke(ctx):
    msg = await ctx.send("⚠️ Es-tu sûr ? Réponds `oui` dans 10s.")
    try:
        reply = await bot.wait_for("message", timeout=10, check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
        if reply.content.lower() == "oui":
            pos = ctx.channel.position
            new_ch = await ctx.channel.clone(reason=f"Nuke par {ctx.author}")
            await ctx.channel.delete()
            await new_ch.edit(position=pos)
            await new_ch.send("💥 Salon recréé !")
    except asyncio.TimeoutError:
        await msg.edit(content="❌ Nuke annulé.")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def hide(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    await channel.set_permissions(ctx.guild.default_role, view_channel=False)
    await ctx.send(f"👁️ {channel.mention} caché.", delete_after=5)

@bot.command()
@commands.has_permissions(manage_channels=True)
async def unhide(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    await channel.set_permissions(ctx.guild.default_role, view_channel=True)
    await ctx.send(f"👁️ {channel.mention} visible.")

@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author
    roles = [r.mention for r in member.roles[1:]] or ["Aucun"]
    e = discord.Embed(title=f"👤 {member}", color=0xFFFFFF)
    e.set_thumbnail(url=member.display_avatar.url)
    e.add_field(name="ID", value=member.id, inline=True)
    e.add_field(name="Pseudo", value=member.display_name, inline=True)
    e.add_field(name="Bot ?", value="Oui" if member.bot else "Non", inline=True)
    e.add_field(name="Compte créé", value=member.created_at.strftime("%d/%m/%Y"), inline=True)
    e.add_field(name="Rejoint le", value=member.joined_at.strftime("%d/%m/%Y"), inline=True)
    e.add_field(name=f"Rôles ({len(member.roles)-1})", value=" ".join(roles[-5:]), inline=False)
    await ctx.send(embed=e)

@bot.command()
async def serverinfo(ctx):
    g = ctx.guild
    e = discord.Embed(title=f"🏰 {g.name}", color=0xFFFFFF)
    if g.icon:
        e.set_thumbnail(url=g.icon.url)
    e.add_field(name="Propriétaire", value=str(g.owner), inline=True)
    e.add_field(name="Membres", value=g.member_count, inline=True)
    e.add_field(name="Salons", value=len(g.channels), inline=True)
    e.add_field(name="Rôles", value=len(g.roles), inline=True)
    e.add_field(name="Boosts", value=g.premium_subscription_count, inline=True)
    e.add_field(name="Créé le", value=g.created_at.strftime("%d/%m/%Y"), inline=True)
    await ctx.send(embed=e)

@bot.command()
async def avatar(ctx, member: discord.Member = None):
    member = member or ctx.author
    e = discord.Embed(title=f"🖼️ Avatar de {member}", color=0xFFFFFF)
    e.set_image(url=member.display_avatar.url)
    await ctx.send(embed=e)

@bot.command()
async def roleinfo(ctx, *, role: discord.Role):
    e = discord.Embed(title=f"🎭 {role.name}", color=0xFFFFFF)
    e.add_field(name="ID", value=role.id, inline=True)
    e.add_field(name="Membres", value=len(role.members), inline=True)
    e.add_field(name="Mentionnable", value="Oui" if role.mentionable else "Non", inline=True)
    e.add_field(name="Créé le", value=role.created_at.strftime("%d/%m/%Y"), inline=True)
    await ctx.send(embed=e)

@bot.command()
async def snipe(ctx):
    data = snipe_data.get(ctx.channel.id)
    if not data:
        return await ctx.send("❌ Aucun message récemment supprimé.")
    e = discord.Embed(description=data["content"], color=0xFFFFFF, timestamp=data["timestamp"])
    e.set_author(name=data["author"], icon_url=data["avatar"])
    e.set_footer(text="Message supprimé")
    await ctx.send(embed=e)

@bot.command()
async def editsnipe(ctx):
    data = edit_snipe.get(ctx.channel.id)
    if not data:
        return await ctx.send("❌ Aucun message récemment édité.")
    e = discord.Embed(color=0xFFFFFF, timestamp=data["timestamp"])
    e.set_author(name=data["author"], icon_url=data["avatar"])
    e.add_field(name="Avant", value=data["before"], inline=False)
    e.add_field(name="Après", value=data["after"], inline=False)
    e.set_footer(text="Message édité")
    await ctx.send(embed=e)

@bot.command()
async def botinfo(ctx):
    e = discord.Embed(title="🤖 Bot Info", color=0xFFFFFF)
    e.add_field(name="Latence", value=f"{round(bot.latency*1000)}ms", inline=True)
    e.add_field(name="Serveurs", value=len(bot.guilds), inline=True)
    e.add_field(name="Commandes", value=len(bot.commands), inline=True)
    e.set_thumbnail(url=bot.user.display_avatar.url)
    await ctx.send(embed=e)

@bot.command()
@commands.has_permissions(manage_messages=True)
async def embed(ctx, *, text: str):
    parts = [p.strip() for p in text.split("|")]
    title = parts[0] if len(parts) > 0 else "Embed"
    desc  = parts[1] if len(parts) > 1 else ""
    color = 0xFFFFFF
    if len(parts) > 2:
        try:
            color = int(parts[2].lstrip("#"), 16)
        except ValueError:
            pass
    await ctx.message.delete()
    await ctx.send(embed=discord.Embed(title=title, description=desc, color=color))

@bot.command()
@commands.has_permissions(manage_messages=True)
async def say(ctx, *, message: str):
    await ctx.message.delete()
    await ctx.send(message)

@bot.command()
async def afk(ctx, *, reason="AFK"):
    afk_users[ctx.author.id] = reason
    await ctx.send(f"💤 **{ctx.author.display_name}** est AFK : *{reason}*", delete_after=10)

@bot.command()
async def poll(ctx, *, question: str):
    e = discord.Embed(title="📊 Sondage", description=question, color=0xFFFFFF)
    e.set_footer(text=f"Sondage par {ctx.author}")
    msg = await ctx.send(embed=e)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")

@bot.command()
async def timer(ctx, seconds: int):
    if seconds < 1 or seconds > 3600:
        return await ctx.send("❌ Entre 1 et 3600 secondes.")
    await ctx.send(f"⏳ Timer de **{seconds}s** lancé !")
    await asyncio.sleep(seconds)
    await ctx.send(f"⏰ {ctx.author.mention} Ton timer est terminé !")

@bot.command()
async def ping(ctx):
    await ctx.send(embed=discord.Embed(description=f"🏓 Pong ! `{round(bot.latency*1000)}ms`", color=0xFFFFFF))

@bot.command()
@commands.has_permissions(manage_roles=True)
async def addrole(ctx, member: discord.Member, *, role: discord.Role):
    await member.add_roles(role)
    await ctx.send(f"✅ Rôle **{role.name}** ajouté à **{member}**.")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def removerole(ctx, member: discord.Member, *, role: discord.Role):
    await member.remove_roles(role)
    await ctx.send(f"✅ Rôle **{role.name}** retiré de **{member}**.")

@bot.command()
@commands.has_permissions(manage_nicknames=True)
async def rename(ctx, member: discord.Member, *, nickname: str):
    await member.edit(nick=nickname)
    await ctx.send(embed=mod_embed("✅ Pseudo changé", f"Le pseudo de **{member}** a été changé en **{nickname}**."))

@bot.command()
@commands.has_permissions(manage_channels=True)
async def renamechannel(ctx, *, new_name: str):
    old_name = ctx.channel.name
    await ctx.channel.edit(name=new_name)
    await ctx.send(embed=mod_embed("✅ Salon renommé", f"**#{old_name}** → **#{new_name}**"))

@bot.command()
@commands.has_permissions(manage_messages=True)
async def announce(ctx, *, message: str):
    ch = discord.utils.get(ctx.guild.text_channels, name="annonces") or \
         discord.utils.get(ctx.guild.text_channels, name="announcements")
    if not ch:
        return await ctx.send("❌ Salon `#annonces` introuvable.")
    e = discord.Embed(title="📢 Annonce", description=message, color=0xFFFFFF, timestamp=datetime.datetime.utcnow())
    e.set_footer(text=f"Par {ctx.author}", icon_url=ctx.author.display_avatar.url)
    await ch.send(embed=e)
    await ctx.send(f"✅ Annonce envoyée dans {ch.mention}.")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Tu n'as pas les permissions nécessaires.", delete_after=5)
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Membre introuvable.", delete_after=5)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Argument manquant. Utilise `{PREFIX}help`.", delete_after=5)
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        await ctx.send(f"❌ Erreur : `{error}`", delete_after=8)

ROLES_AUTORISES = ["💼  | Gérant Staff", "👑 | Fondateur", "👑 | Co-Fondateur"]

@bot.check
async def global_check(ctx):
    if ctx.author.id in [1327982910619516999, 1364650566684512346]: 
        return True
    user_roles = [r.name for r in ctx.author.roles]
    if any(r in user_roles for r in ROLES_AUTORISES):
        return True
    return False

TICKET_CATEGORIES = {
    "recrutement_cm": {"label": "Recrutement-CM", "category": "Ticket Recrutement CM", "roles": ["👑 | Fondateur", "👑 | Co-Fondateur", "💼  | Gérant Staff"], "color": 0xFFFFFF, "emoji": "🔖"},
    "ticket_autre": {"label": "Ticket-autre", "category": "Ticket Autre", "roles": ["🔧  | Modérateur", "💼  | Gérant Staff"], "color": 0xFFFFFF, "emoji": "❓"},
    "recrutement_staff": {"label": "Recrutement-STAFF", "category": "Ticket Recrutement Staff", "roles": ["👑 | Fondateur", "👑 | Co-Fondateur", "💼  | Gérant Staff"], "color": 0xFFFFFF, "emoji": "💼"},
    "recrutement_graphique": {"label": "Recrutement-Graphique", "category": "Ticket Recrutement Graphique", "roles": ["👑 | Fondateur", "👑 | Co-Fondateur", "💼  | Gérant Staff"], "color": 0xFFFFFF, "emoji": "🎨"},
    "ticket_shop": {"label": "Ticket-shop", "category": "Ticket Shop", "roles": ["🔧  | Modérateur", "💼  | Gérant Staff", "🎨 | Graphiste"], "color": 0xFFFFFF, "emoji": "🎫"},
}

class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=cfg["label"], value=key, emoji=cfg["emoji"]) for key, cfg in TICKET_CATEGORIES.items()]
        super().__init__(placeholder="Choisis une catégorie...", min_values=1, max_values=1, options=options, custom_id="ticket_select")

    async def callback(self, interaction: discord.Interaction):
        key = self.values[0]
        cfg = TICKET_CATEGORIES[key]
        guild = interaction.guild
        member = interaction.user
        existing = discord.utils.get(guild.text_channels, name=f"ticket-{member.name.lower().replace(' ', '-')}")
        if existing:
            return await interaction.response.send_message(f"❌ Tu as déjà un ticket ouvert : {existing.mention}", ephemeral=True)
        category = discord.utils.get(guild.categories, name=cfg["category"])
        if not category:
            category = await guild.create_category(cfg["category"])
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }
        for role_name in cfg["roles"]:
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_messages=True)
        channel = await category.create_text_channel(name=f"ticket-{member.name.lower().replace(' ', '-')}", overwrites=overwrites, topic=f"Ticket de {member} | {cfg['label']}")
        e = discord.Embed(title=f"{cfg['emoji']} Ticket – {cfg['label']}", description=f"Bonjour {member.mention} ! 👋\n\nUn membre du staff va te répondre dans les plus brefs délais.\nDécris ta demande en détail ci-dessous.\n\nPour fermer ce ticket, clique sur 🔒 ci-dessous.", color=0xFFFFFF, timestamp=datetime.datetime.utcnow())
        e.set_footer(text=f"Ticket ouvert par {member}", icon_url=member.display_avatar.url)
        await channel.send(embed=e, view=TicketControlView())
        await interaction.response.send_message(f"✅ Ton ticket a été créé : {channel.mention}", ephemeral=True)

class TicketSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Fermer le ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        channel = interaction.channel
        closed_category = discord.utils.get(guild.categories, name="Ticket Fermé")
        if not closed_category:
            closed_category = await guild.create_category("Ticket Fermé")
        for overwrite_target in list(channel.overwrites):
            if isinstance(overwrite_target, discord.Member) and overwrite_target != guild.me:
                await channel.set_permissions(overwrite_target, view_channel=False, send_messages=False)
        await channel.set_permissions(guild.default_role, view_channel=False, send_messages=False)
        await channel.edit(category=closed_category, name=f"fermé-{channel.name}")
        e = discord.Embed(title="🔒 Ticket fermé", description=f"Ce ticket a été fermé par {interaction.user.mention}.\nIl est maintenant archivé.", color=0xFFFFFF, timestamp=datetime.datetime.utcnow())
        await interaction.response.send_message(embed=e)

    @discord.ui.button(label="Supprimer", style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="delete_ticket")
    async def delete_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        roles_autorises = ["👑 | Fondateur", "👑 | Co-Fondateur"]
        user_roles = [r.name for r in interaction.user.roles]
        if not any(r in user_roles for r in roles_autorises):
            return await interaction.response.send_message("❌ Seuls les Fondateurs peuvent supprimer définitivement un ticket.", ephemeral=True)
        e = discord.Embed(title="🗑️ Suppression", description=f"Ticket supprimé par {interaction.user.mention}. Suppression dans **5 secondes**.", color=0xFFFFFF, timestamp=datetime.datetime.utcnow())
        await interaction.response.send_message(embed=e)
        await asyncio.sleep(5)
        await interaction.channel.delete(reason=f"Ticket supprimé par {interaction.user}")

    @discord.ui.button(label="Sauvegarder", style=discord.ButtonStyle.secondary, emoji="💾", custom_id="save_ticket")
    async def save_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        import io
        messages = []
        async for msg in interaction.channel.history(limit=200, oldest_first=True):
            if not msg.author.bot:
                messages.append(f"[{msg.created_at.strftime('%H:%M')}] {msg.author}: {msg.content}")
        transcript = "\n".join(messages) if messages else "Aucun message."
        file = discord.File(fp=io.StringIO(transcript), filename=f"transcript-{interaction.channel.name}.txt")
        await interaction.user.send(f"📄 Transcript du ticket **{interaction.channel.name}** :", file=file)
        await interaction.response.send_message("✅ Transcript envoyé en MP !", ephemeral=True)

    @discord.ui.button(label="Ajouter un membre", style=discord.ButtonStyle.success, emoji="➕", custom_id="add_member")
    async def add_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Mentionne le membre à ajouter (ex: @pseudo) :", ephemeral=True)
        try:
            msg = await bot.wait_for("message", timeout=30, check=lambda m: m.author == interaction.user and m.channel == interaction.channel and m.mentions)
            for member in msg.mentions:
                await interaction.channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True)
            await interaction.channel.send(f"✅ {', '.join(m.mention for m in msg.mentions)} ajouté(s) au ticket.")
            await msg.delete()
        except asyncio.TimeoutError:
            pass

@bot.command()
@commands.has_permissions(administrator=True)
async def ticket(ctx):
    await ctx.message.delete()
    e = discord.Embed(title="🎫 Support – GraphStudio", description="Pour créer un ticket, sélectionne une catégorie dans le menu ci-dessous.\n\n*Propulsé par l'équipe GraphStudio* 🔥", color=0xFFFFFF, timestamp=datetime.datetime.utcnow())
    e.set_footer(text="GraphStudio • Support")
    if ctx.guild.icon:
        e.set_thumbnail(url=ctx.guild.icon.url)
    await ctx.send(embed=e, view=TicketSelectView())

@bot.event
async def on_ready():
    bot.add_view(TicketControlView())
    bot.add_view(TicketSelectView())
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="discord.gg/graphstudio"))
    print(f"✅ Connecté en tant que {bot.user} (ID: {bot.user.id})")
        
@bot.event
async def on_member_update(before, after):
    # Message boost
    if after.premium_since and not before.premium_since:
        channel = bot.get_channel(1495462875609698305)
        if channel:
            e = discord.Embed(
                title="🚀 Merci d'avoir boosté le serveur !",
                description=(
                    f"Un immense merci à {after.mention} pour le boost de **GraphStudio** !\n\n"
                    f"🚀 Avantages exclusifs\n"
                    f"🎨 Salon dédié boosteurs\n"
                    f"🎁 Giveaways boostés"
                ),
                color=0xFFFFFF,
                timestamp=datetime.datetime.utcnow()
            )
            e.set_thumbnail(url=after.display_avatar.url)
            e.set_footer(text="GraphStudio", icon_url=after.guild.icon.url if after.guild.icon else None)
            await channel.send(embed=e)

    # VIP auto-remove si plus booster
    booster_role = discord.utils.get(after.guild.roles, name="🔮| Booster")
    vip_role = discord.utils.get(after.guild.roles, name="⭐️ | VIP GraphStudio")
    if booster_role and vip_role:
        if booster_role in before.roles and booster_role not in after.roles:
            if vip_role in after.roles:
                await after.remove_roles(vip_role, reason="Plus booster")
                try:
                    await after.send(f"💔 Tu as perdu le rôle **{vip_role.name}** car tu ne boostes plus le serveur.")
                except Exception:
                    pass

@bot.command()
@commands.has_permissions(manage_messages=True)
async def img(ctx, *urls: str):
    await ctx.message.delete()
    if not urls:
        return await ctx.send("❌ Donne au moins une URL. Ex: `+img url1 url2 url3`", delete_after=5)
    import aiohttp
    files = []
    async with aiohttp.ClientSession() as session:
        for i, url in enumerate(urls[:4]):
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    ext = url.split(".")[-1].split("?")[0] or "png"
                    files.append(discord.File(fp=__import__("io").BytesIO(data), filename=f"image{i+1}.{ext}"))
    if files:
        await ctx.send(files=files)
    else:
        await ctx.send("❌ Impossible de récupérer les images.", delete_after=5)

@bot.command()
@commands.has_permissions(administrator=True)
async def dmall(ctx, *, message: str):
    await ctx.send("📨 Envoi des DMs en cours...", delete_after=5)
    success = 0
    failed = 0
    for member in ctx.guild.members:
        if not member.bot:
            try:
                e = discord.Embed(
                    title=f"📢 Message de {ctx.guild.name}",
                    description=message,
                    color=0xFFFFFF,
                    timestamp=datetime.datetime.utcnow()
                )
                e.set_footer(text=f"Envoyé par {ctx.author}", icon_url=ctx.author.display_avatar.url)
                if ctx.guild.icon:
                    e.set_thumbnail(url=ctx.guild.icon.url)
                await member.send(embed=e)
                success += 1
                await asyncio.sleep(1)
            except Exception:
                failed += 1
    await ctx.send(embed=mod_embed("📨 DM terminé", f"✅ Envoyé : **{success}**\n❌ Échoué : **{failed}**"))

@bot.event
async def on_member_join(member):
    # Message règlement
    reglement_channel = bot.get_channel(1495455893863665714)
    if reglement_channel:
        await reglement_channel.send(
            f"{member.mention} N'oublie pas de cocher et d'accepter le règlement !",
            delete_after=30
        )

    # Message de bienvenue
    channel = bot.get_channel(1495455717220417709)
    if not channel:
        return

    inviter = None
    try:
        invites = await member.guild.invites()
        for invite in invites:
            if invite.uses > 0:
                inviter = invite.inviter
                break
    except Exception:
        pass

    guild = member.guild
    e = discord.Embed(
        title="🎨 Bienvenue dans GraphStudio",
        description=(
            f"Bienvenue **{member.name}**, installe-toi bien parmi nous.\n\n"
            f"🎨 Pour commencer, poste ta première créa dans <#1515420912286175242>\n\n"
            f"🎁 Giveaways, entraide GFX et commandes t'attendent ensuite."
        ),
        color=0xFFFFFF,
        timestamp=datetime.datetime.utcnow()
    )
    e.set_thumbnail(url=member.display_avatar.url)
    e.add_field(name="🔗 Invité par", value=f"{inviter.mention if inviter else 'Inconnu'}", inline=True)
    e.add_field(name="📅 Arrivée", value="1ère fois ici", inline=True)
    e.add_field(name="👥 Membres", value=f"{guild.member_count - 1} au total", inline=True)
    e.set_footer(text="GraphStudio", icon_url=guild.icon.url if guild.icon else None)
    await channel.send(embed=e)

@bot.command()
@commands.has_permissions(manage_messages=True)
async def rate(ctx, member: discord.Member = None):
    import random
    note = random.randint(1, 10)
    bars = "█" * note + "░" * (10 - note)
    e = discord.Embed(title="🎨 Notation GFX", description=f"{'**' + member.mention + '**' if member else 'Ta création'} obtient :\n\n`{bars}` **{note}/10**", color=0xFFFFFF)
    await ctx.send(embed=e)

@bot.command()
@commands.has_permissions(manage_messages=True)
async def gfx(ctx, *, titre: str):
    e = discord.Embed(title="🎨 Commande GFX disponible", description=titre, color=0xFFFFFF, timestamp=datetime.datetime.utcnow())
    e.set_footer(text=f"Posté par {ctx.author}", icon_url=ctx.author.display_avatar.url)
    await ctx.message.delete()
    await ctx.send(embed=e)

@bot.command()
@commands.has_permissions(manage_messages=True)
async def concours(ctx, *, description: str):
    e = discord.Embed(title="🏆 Concours GFX", description=description, color=0xFFFFFF, timestamp=datetime.datetime.utcnow())
    e.set_footer(text=f"GraphStudio • Organisé par {ctx.author}")
    msg = await ctx.send(embed=e)
    await msg.add_reaction("🎨")
    await msg.add_reaction("🏆")
    await ctx.message.delete()

@bot.command()
@commands.has_permissions(manage_messages=True)
async def showcase(ctx, member: discord.Member, *, description: str):
    e = discord.Embed(title="⭐ Showcase GFX", description=f"Félicitations à {member.mention} !\n\n{description}", color=0xFFFFFF, timestamp=datetime.datetime.utcnow())
    e.set_thumbnail(url=member.display_avatar.url)
    e.set_footer(text="GraphStudio • Showcase")
    await ctx.message.delete()
    await ctx.send(embed=e)

@bot.command()
@commands.has_permissions(manage_messages=True)
async def feedback(ctx, member: discord.Member, *, avis: str):
    e = discord.Embed(title="💬 Feedback GFX", description=f"Feedback pour {member.mention} :\n\n{avis}", color=0xFFFFFF, timestamp=datetime.datetime.utcnow())
    e.set_footer(text=f"Par {ctx.author}", icon_url=ctx.author.display_avatar.url)
    await ctx.message.delete()
    await ctx.send(embed=e)
                
bot.run(TOKEN)
