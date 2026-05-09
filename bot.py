import discord
from discord.ext import commands
import asyncio
import datetime
import json
import os
import re
from collections import defaultdict

# ──────────────────────────────────────────────
#  CONFIGURATION – modifie ces valeurs
# ──────────────────────────────────────────────
TOKEN = os.environ.get("DISCORD_TOKEN")
PREFIX = "+"                      # Préfixe des commandes
MUTE_ROLE_NAME = "Muted"          # Nom du rôle muet (créé auto si absent)
LOG_CHANNEL_NAME = "mod-logs"     # Salon de logs (optionnel)
# ──────────────────────────────────────────────

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

# Stockage en mémoire
snipe_data   = {}   # {channel_id: {content, author, timestamp}}
edit_snipe   = {}   # {channel_id: {before, after, author, timestamp}}
warnings     = defaultdict(list)   # {user_id: [raisons]}
afk_users    = {}   # {user_id: raison}
slowmode_map = {}   # {channel_id: secondes}

# ══════════════════════════════════════════════
#  ÉVÉNEMENTS
# ══════════════════════════════════════════════

@bot.event
async def on_ready():
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{PREFIX}discord.gg/graphstudio"
        )
    )
    print(f"✅  Connecté en tant que {bot.user} (ID: {bot.user.id})")

@bot.event
async def on_message_delete(message):
    if message.author.bot:
        return
    snipe_data[message.channel.id] = {
        "content":   message.content or "[Aucun texte]",
        "author":    str(message.author),
        "avatar":    str(message.author.display_avatar.url),
        "timestamp": datetime.datetime.utcnow()
    }

@bot.event
async def on_message_edit(before, after):
    if before.author.bot or before.content == after.content:
        return
    edit_snipe[before.channel.id] = {
        "before":    before.content or "[Aucun texte]",
        "after":     after.content  or "[Aucun texte]",
        "author":    str(before.author),
        "avatar":    str(before.author.display_avatar.url),
        "timestamp": datetime.datetime.utcnow()
    }

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    # Détection AFK
    if message.author.id in afk_users:
        reason = afk_users.pop(message.author.id)
        await message.channel.send(
            f"👋 Bienvenue {message.author.mention} ! Tu n'es plus AFK (tu l'étais : *{reason}*).",
            delete_after=8
        )
    # Mentions d'utilisateurs AFK
    for user in message.mentions:
        if user.id in afk_users:
            await message.channel.send(
                f"💤 **{user.display_name}** est AFK : *{afk_users[user.id]}*",
                delete_after=8
            )
    await bot.process_commands(message)

# ══════════════════════════════════════════════
#  AIDE
# ══════════════════════════════════════════════

@bot.command(name="help")
async def help_cmd(ctx, category: str = None):
    categories = {
        "mod": {
            "emoji": "🔨",
            "title": "Modération",
            "cmds": [
                ("+ban   [user] [raison]",   "Bannit un membre"),
                ("+unban [user#0000]",        "Débannit un utilisateur"),
                ("+kick  [user] [raison]",    "Expulse un membre"),
                ("+mute  [user] [durée] [raison]", "Mute (ex: 10m, 1h)"),
                ("+unmute [user]",            "Démute un membre"),
                ("+warn  [user] [raison]",    "Avertit un membre"),
                ("+warns [user]",             "Liste les warnings"),
                ("+clearwarns [user]",        "Efface les warnings"),
                ("+softban [user] [raison]",  "Ban+unban (purge messages)"),
                ("+massban [@u1 @u2 ...]",    "Bannit plusieurs membres"),
            ]
        },
        "channel": {
            "emoji": "📢",
            "title": "Canaux",
            "cmds": [
                ("+clear  [n]",              "Supprime n messages"),
                ("+purgeuser [user] [n]",    "Supprime les msgs d'un user"),
                ("+lock   [salon]",          "Verrouille le salon"),
                ("+unlock [salon]",          "Déverrouille le salon"),
                ("+slowmode [secondes]",     "Définit le slowmode"),
                ("+nuke",                    "Recrée le salon (clean total)"),
                ("+hide",                    "Cache le salon"),
                ("+unhide",                  "Révèle le salon"),
            ]
        },
        "info": {
            "emoji": "ℹ️",
            "title": "Informations",
            "cmds": [
                ("+userinfo [user]",         "Infos sur un utilisateur"),
                ("+serverinfo",              "Infos sur le serveur"),
                ("+avatar  [user]",          "Avatar d'un utilisateur"),
                ("+roleinfo [role]",         "Infos sur un rôle"),
                ("+snipe",                   "Dernier message supprimé"),
                ("+editsnipe",               "Dernier message édité"),
                ("+botinfo",                 "Infos sur le bot"),
            ]
        },
        "util": {
            "emoji": "🛠️",
            "title": "Utilitaires",
            "cmds": [
                ("+embed [titre] | [desc]",  "Crée un embed"),
                ("+say   [message]",         "Bot répète un message"),
                ("+afk   [raison]",          "Passe en mode AFK"),
                ("+poll  [question]",        "Lance un sondage"),
                ("+timer [secondes]",        "Lance un timer"),
                ("+ping",                    "Latence du bot"),
                ("+addrole [user] [role]",   "Ajoute un rôle"),
                ("+removerole [user] [role]","Retire un rôle"),
                ("+nick [user] [nouveau]",   "Change le pseudo"),
                ("+announce [msg]",          "Annonce dans #annonces"),
            ]
        }
    }

    if category and category.lower() in categories:
        c = categories[category.lower()]
        embed = discord.Embed(
            title=f"{c['emoji']} Commandes – {c['title']}",
            color=0x5865F2
        )
        for cmd, desc in c["cmds"]:
            embed.add_field(name=f"`{cmd}`", value=desc, inline=False)
        embed.set_footer(text=f"Préfixe : {PREFIX}")
        return await ctx.send(embed=embed)

    embed = discord.Embed(
        title="📖 Aide – Bot Modération",
        description=(
            "Utilise `+help [catégorie]` pour voir les commandes détaillées.\n\n"
            "**Catégories disponibles :**"
        ),
        color=0x5865F2,
        timestamp=datetime.datetime.utcnow()
    )
    for key, c in categories.items():
        embed.add_field(
            name=f"{c['emoji']} `+help {key}`",
            value=c["title"],
            inline=True
        )
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text=f"Bot lancé par {ctx.author}", icon_url=ctx.author.display_avatar.url)
    await ctx.send(embed=embed)

# ══════════════════════════════════════════════
#  MODÉRATION
# ══════════════════════════════════════════════

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

def mod_embed(title, description, color=0xED4245, **fields):
    e = discord.Embed(title=title, description=description, color=color, timestamp=datetime.datetime.utcnow())
    for k, v in fields.items():
        e.add_field(name=k, value=v, inline=True)
    return e

# ── BAN ──────────────────────────────────────

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
            e = mod_embed("✅ Débanni", f"**{entry.user}** a été débanni.", color=0x57F287, Modérateur=str(ctx.author))
            return await ctx.send(embed=e)
    await ctx.send(f"❌ Utilisateur `{user_tag}` introuvable dans les bans.")

@bot.command()
@commands.has_permissions(ban_members=True)
async def softban(ctx, member: discord.Member, *, reason="Aucune raison fournie"):
    await member.ban(reason=f"Softban: {reason}", delete_message_days=7)
    await ctx.guild.unban(member)
    e = mod_embed("🔨 Softban", f"**{member}** a été softban (messages supprimés).", Raison=reason, Modérateur=str(ctx.author))
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

# ── KICK ─────────────────────────────────────

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="Aucune raison fournie"):
    await member.kick(reason=reason)
    e = mod_embed("👢 Expulsé", f"**{member}** a été expulsé.", Raison=reason, Modérateur=str(ctx.author))
    await ctx.send(embed=e)
    await log_action(ctx.guild, e)

# ── MUTE ─────────────────────────────────────

def parse_duration(duration_str):
    """Convertit '10m', '1h', '30s' en secondes."""
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
            reason = f"{duration} {reason}".strip()  # pas une durée valide

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
        e = mod_embed("🔊 Unmute", f"**{member}** a été unmute.", color=0x57F287, Modérateur=str(ctx.author))
        await ctx.send(embed=e)
        await log_action(ctx.guild, e)
    else:
        await ctx.send(f"❌ **{member}** n'est pas mute.")

# ── WARN ─────────────────────────────────────

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
    e = discord.Embed(title=f"⚠️ Avertissements de {member}", color=0xFEE75C)
    for i, entry in enumerate(w, 1):
        e.add_field(name=f"#{i} – {entry['date']}", value=f"**Raison :** {entry['raison']}\n**Par :** {entry['par']}", inline=False)
    await ctx.send(embed=e)

@bot.command()
@commands.has_permissions(manage_messages=True)
async def clearwarns(ctx, member: discord.Member):
    warnings[member.id] = []
    await ctx.send(embed=mod_embed("✅ Warnings effacés", f"Les avertissements de **{member}** ont été supprimés.", color=0x57F287))

# ══════════════════════════════════════════════
#  CANAUX
# ══════════════════════════════════════════════

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):
    if amount < 1 or amount > 500:
        return await ctx.send("❌ Entre 1 et 500 messages.")
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"🗑️ {len(deleted)-1} message(s) supprimé(s).", delete_after=5)

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
    await ctx.send(embed=mod_embed("🔒 Salon verrouillé", f"{channel.mention} est maintenant verrouillé.", color=0xED4245))

@bot.command()
@commands.has_permissions(manage_channels=True)
async def unlock(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    await channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send(embed=mod_embed("🔓 Salon déverrouillé", f"{channel.mention} est maintenant ouvert.", color=0x57F287))

@bot.command()
@commands.has_permissions(manage_channels=True)
async def slowmode(ctx, seconds: int):
    await ctx.channel.edit(slowmode_delay=seconds)
    await ctx.send(f"⏱️ Slowmode défini à **{seconds}s** dans {ctx.channel.mention}.")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def nuke(ctx):
    msg = await ctx.send("⚠️ Es-tu sûr de vouloir recréer ce salon ? Réponds `oui` dans 10s.")
    try:
        reply = await bot.wait_for("message", timeout=10, check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
        if reply.content.lower() == "oui":
            pos = ctx.channel.position
            new_ch = await ctx.channel.clone(reason=f"Nuke par {ctx.author}")
            await ctx.channel.delete()
            await new_ch.edit(position=pos)
            await new_ch.send("💥 Salon recréé avec succès !")
    except asyncio.TimeoutError:
        await msg.edit(content="❌ Nuke annulé.")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def hide(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    await channel.set_permissions(ctx.guild.default_role, view_channel=False)
    await ctx.send(f"👁️ {channel.mention} est maintenant caché.", delete_after=5)

@bot.command()
@commands.has_permissions(manage_channels=True)
async def unhide(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    await channel.set_permissions(ctx.guild.default_role, view_channel=True)
    await ctx.send(f"👁️ {channel.mention} est maintenant visible.")

# ══════════════════════════════════════════════
#  INFORMATIONS
# ══════════════════════════════════════════════

@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author
    roles = [r.mention for r in member.roles[1:]] or ["Aucun"]
    e = discord.Embed(title=f"👤 {member}", color=member.color or 0x5865F2)
    e.set_thumbnail(url=member.display_avatar.url)
    e.add_field(name="ID",            value=member.id,                                    inline=True)
    e.add_field(name="Pseudo",        value=member.display_name,                          inline=True)
    e.add_field(name="Bot ?",         value="Oui" if member.bot else "Non",               inline=True)
    e.add_field(name="Compte créé",   value=member.created_at.strftime("%d/%m/%Y"),        inline=True)
    e.add_field(name="Rejoint le",    value=member.joined_at.strftime("%d/%m/%Y"),         inline=True)
    e.add_field(name=f"Rôles ({len(member.roles)-1})", value=" ".join(roles[-5:]), inline=False)
    await ctx.send(embed=e)

@bot.command()
async def serverinfo(ctx):
    g = ctx.guild
    e = discord.Embed(title=f"🏰 {g.name}", color=0x5865F2)
    if g.icon:
        e.set_thumbnail(url=g.icon.url)
    e.add_field(name="Propriétaire",  value=str(g.owner),                 inline=True)
    e.add_field(name="Membres",       value=g.member_count,               inline=True)
    e.add_field(name="Salons",        value=len(g.channels),              inline=True)
    e.add_field(name="Rôles",         value=len(g.roles),                 inline=True)
    e.add_field(name="Boosts",        value=g.premium_subscription_count, inline=True)
    e.add_field(name="Créé le",       value=g.created_at.strftime("%d/%m/%Y"), inline=True)
    await ctx.send(embed=e)

@bot.command()
async def avatar(ctx, member: discord.Member = None):
    member = member or ctx.author
    e = discord.Embed(title=f"🖼️ Avatar de {member}", color=0x5865F2)
    e.set_image(url=member.display_avatar.url)
    await ctx.send(embed=e)

@bot.command()
async def roleinfo(ctx, *, role: discord.Role):
    e = discord.Embed(title=f"🎭 {role.name}", color=role.color)
    e.add_field(name="ID",          value=role.id,                          inline=True)
    e.add_field(name="Membres",     value=len(role.members),                inline=True)
    e.add_field(name="Mentionnable",value="Oui" if role.mentionable else "Non", inline=True)
    e.add_field(name="Créé le",     value=role.created_at.strftime("%d/%m/%Y"), inline=True)
    await ctx.send(embed=e)

@bot.command()
async def snipe(ctx):
    data = snipe_data.get(ctx.channel.id)
    if not data:
        return await ctx.send("❌ Aucun message récemment supprimé dans ce salon.")
    e = discord.Embed(description=data["content"], color=0xED4245, timestamp=data["timestamp"])
    e.set_author(name=data["author"], icon_url=data["avatar"])
    e.set_footer(text="Message supprimé")
    await ctx.send(embed=e)

@bot.command()
async def editsnipe(ctx):
    data = edit_snipe.get(ctx.channel.id)
    if not data:
        return await ctx.send("❌ Aucun message récemment édité dans ce salon.")
    e = discord.Embed(color=0xFEE75C, timestamp=data["timestamp"])
    e.set_author(name=data["author"], icon_url=data["avatar"])
    e.add_field(name="Avant", value=data["before"], inline=False)
    e.add_field(name="Après", value=data["after"],  inline=False)
    e.set_footer(text="Message édité")
    await ctx.send(embed=e)

@bot.command()
async def botinfo(ctx):
    e = discord.Embed(title="🤖 Bot Info", color=0x5865F2)
    e.add_field(name="Latence",   value=f"{round(bot.latency*1000)}ms", inline=True)
    e.add_field(name="Serveurs",  value=len(bot.guilds),                inline=True)
    e.add_field(name="Commandes", value=len(bot.commands),              inline=True)
    e.set_thumbnail(url=bot.user.display_avatar.url)
    await ctx.send(embed=e)

# ══════════════════════════════════════════════
#  UTILITAIRES
# ══════════════════════════════════════════════

@bot.command()
@commands.has_permissions(manage_messages=True)
async def embed(ctx, *, text: str):
    """Usage : +embed Titre | Description | #couleur(optionnel)"""
    parts = [p.strip() for p in text.split("|")]
    title = parts[0] if len(parts) > 0 else "Embed"
    desc  = parts[1] if len(parts) > 1 else ""
    color = 0x5865F2
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
    await ctx.send(f"💤 **{ctx.author.display_name}** est maintenant AFK : *{reason}*", delete_after=10)

@bot.command()
async def poll(ctx, *, question: str):
    e = discord.Embed(title="📊 Sondage", description=question, color=0x5865F2)
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
    await ctx.send(f"⏰ {ctx.author.mention} Ton timer de **{seconds}s** est terminé !")

@bot.command()
async def ping(ctx):
    await ctx.send(embed=discord.Embed(description=f"🏓 Pong ! `{round(bot.latency*1000)}ms`", color=0x57F287))

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
async def nick(ctx, member: discord.Member, *, nickname: str):
    await member.edit(nick=nickname)
    await ctx.send(f"✅ Pseudo de **{member}** changé en **{nickname}**.")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def announce(ctx, *, message: str):
    ch = discord.utils.get(ctx.guild.text_channels, name="annonces") or \
         discord.utils.get(ctx.guild.text_channels, name="announcements")
    if not ch:
        return await ctx.send("❌ Salon `#annonces` introuvable.")
    e = discord.Embed(title="📢 Annonce", description=message, color=0x5865F2, timestamp=datetime.datetime.utcnow())
    e.set_footer(text=f"Par {ctx.author}", icon_url=ctx.author.display_avatar.url)
    await ch.send(embed=e)
    await ctx.send(f"✅ Annonce envoyée dans {ch.mention}.")

# ══════════════════════════════════════════════
#  GESTION DES ERREURS
# ══════════════════════════════════════════════

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Tu n'as pas les permissions nécessaires.", delete_after=5)
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Membre introuvable.", delete_after=5)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Argument manquant. Utilise `{PREFIX}help`.", delete_after=5)
    elif isinstance(error, commands.CommandNotFound):
        pass  # Ignore les commandes inconnues
    else:
        await ctx.send(f"❌ Erreur : `{error}`", delete_after=8)

# ══════════════════════════════════════════════
#  LANCEMENT
# ══════════════════════════════════════════════

bot.run(TOKEN)
