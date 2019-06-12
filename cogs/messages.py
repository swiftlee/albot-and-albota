import discord
from discord.ext import commands

import asyncio

import cogs.CONSTANTS as CONSTANTS
from database.database import SQLCursor, SQLConnection

reacted_messages = {}

class ALBotMessageDeletionHandlers(commands.Cog, name='Message Deletion Handlers'):
    """ Functions for handling tracked messages """
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """ Checks reactions and deletes tracked messages when necessary. """
        if payload.user_id == self.bot.user.id:
            return
        if payload.emoji.name == CONSTANTS.REACTION_DELETE:
            is_tracked = False
            sender_uid = None
            with SQLCursor(self.db) as cur:
                cur.execute("SELECT messid, sender_uid FROM tracked_messages WHERE messid=?", (payload.message_id,))
                row = cur.fetchone()
                if row:
                    is_tracked = True
                    sender_uid = row[1]

            if is_tracked:
                reacting_member = self.bot.get_guild(payload.guild_id).get_member(payload.user_id)
                can_delete = self.bot.get_channel(payload.channel_id).permissions_for(reacting_member).manage_messages
                if payload.user_id == sender_uid or can_delete:
                    relevant_message = await self.bot.get_channel(payload.channel_id).fetch_message(payload.message_id)
                    await relevant_message.delete()

async def track(message, author=None):
    """ Marks a message in the database so that it will be automatically
        deleted if the sender or an admin reacts with the 'trash' emoji
    """
    await message.add_reaction(CONSTANTS.REACTION_DELETE)
    sql_db = SQLConnection()
    aid = 0
    if author:
        aid = author.id
    with SQLCursor(sql_db) as cur:
                cur.execute("INSERT INTO tracked_messages (messid, sender_uid, track_time) VALUES (?, ?, ?);", (message.id, aid, message.created_at))

class ALBotFactorialHandler(commands.Cog, name='Factorial Handler'):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, msg):
        """Checks message for factorial format using regex."""
        if msg.author != self.bot.user:
            import re
            filtered_msg = re.findall('{(?:[0-9]|[1-8](?:[0-9]{1,2})?)!}', msg.content)
            if filtered_msg is not None:
                group_len = len(filtered_msg)
                factorial = 'Factorial: `{}! = {}`' if group_len == 1 else 'The following factorials were calculated as:```'
                import math
                if group_len > 1:
                    for i in range(0, group_len):
                        num = int((filtered_msg[i].split('!')[0])[1:])
                        product = math.factorial(num)
                        factorial += '\n\n{}! = {}'.format(num, product)
                    await msg.channel.send(factorial + '```')
                elif group_len == 1:
                    try:
                        num = int((filtered_msg[0].split('!')[0])[1:])
                        await msg.channel.send(factorial.format(num, math.factorial(num)))
                    except discord.HTTPException as e:
                        await msg.channel.send('Cannot post answer due to excessive character count! Maximum factorial allowed is `801!`.')


class ALBotMessageClear(commands.Cog, name='Message Clear'):
    """Functions for handling message deletion in channels"""
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        pass # TODO: check the set mapped to the user id to handle emoji interactions in this cog, needs debugging

    @commands.command()
    async def clear(self, ctx, a_number=0):
        global reacted_messages
        # Checks if number is positive int
        if not a_number > 0:
            await ctx.channel.send(content="Please input a number larger than zero")
            return

        can_delete = self.bot.get_channel(ctx.channel.id).permissions_for(ctx.author).manage_messages
        if can_delete:
            buffer = 1
            # Warns user if the number is greater than 20
            if a_number > 20:
                buffer += 1
                user_message = ctx.channel.last_message
                user = None
                msg = await ctx.channel.send("WARNING: You are about to delete more than 20 messages, are you sure you want to do this?")
                reactions = ["✅", "❌"]
                for emoji in reactions:
                    await ctx.channel.last_message.add_reaction(emoji)

                try:
                    reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=lambda reaction, user: reaction.emoji == '✅')
                    # create a map in this format: {userId, {messageIds}}
                    reacted_messages += {user.id: str(reacted_messages.get(user.id, 0)) + "," + str(msg.id) if reacted_messages.get(user.id, 0) is not None else str(msg.id)}
                except asyncio.TimeoutError:
                    msgs = reacted_messages[user.id]
                    if str(msg.id) in str(msgs.get(user.id, 0)):
                        reacted_messages[user.id] = reacted_messages.get(user.id, 0).replace(str(msg.id), '')
                    await ctx.channel.send('Command Timeout')
                    return

            async for message in ctx.channel.history(limit=a_number+buffer):
                if not message.pinned:
                    relevant_message = await self.bot.get_channel(ctx.channel.id).fetch_message(message.id)
                    await relevant_message.delete()
                    await asyncio.sleep(0.4)
        #    deleted = await ctx.channel.purge(limit=a_number+buffer, check=)
            await ctx.channel.send(content='@{} Successfully deleted {} messages'.format(ctx.author, a_number))

def setup(bot):
    bot.add_cog(ALBotMessageDeletionHandlers(bot, SQLConnection()))
    bot.add_cog(ALBotFactorialHandler(bot))
    bot.add_cog(ALBotMessageClear(bot))
