from discord import Embed, Colour, Streaming
from core.client import dc
from core.utils import get_nick, join_and

#for check_in_timeout discord unix epoch timestamp
import time

from bot.main import bf2_servers

class Embeds:
	""" This class generates discord embeds for various match states """

	def __init__(self, match):
		self.m = match
		# self.
		self.footer = dict(
			text=f"Match id: {self.m.id}",
			icon_url=f"https://cdn.discordapp.com/avatars/{dc.user.id}/{dc.user.avatar}.png?size=64"
		)

	def check_in(self, not_ready):
		embed = Embed(
			colour=Colour(0xf5d858),
			title=self.m.gt("__**{queue}** is now on the check-in stage!__").format(
				queue=self.m.queue.name[0].upper()+self.m.queue.name[1:]
			)
		)
		embed.add_field(
			name=self.m.gt("Waiting on:"),
			value="\n".join((f" \u200b <@{p.id}>" for p in not_ready)),
			inline=False
		)
		if not len(self.m.check_in.maps):
			# add check-in discord timestamp
			check_in_timeout_epoch = str(int(time.time()) + self.m.cfg['check_in_timeout'])
			embed.add_field(
				name="—",
				value="\n".join([
					self.m.gt("Please react with {ready_emoji} to **check-in** or {not_ready_emoji} to **abort**!").format(
						ready_emoji=self.m.check_in.READY_EMOJI,
						not_ready_emoji=self.m.check_in.NOT_READY_EMOJI
					),
					self.m.gt("\u1CBC\u1CBC\u1CBC\u1CBC\u1CBC\u1CBC\u1CBC\u1CBC\u1CBC\u1CBC\u1CBC\u1CBC\u1CBC\u1CBC\u1CBC\u1CBC\u1CBC\u1CBC\u1CBC\u1CBC\u1CBC**within:** <t:" + check_in_timeout_epoch + ":R>").format(
						not_ready_emoji=self.m.check_in.NOT_READY_EMOJI
					) + "\n\u200b"
				]),
				inline=False
			)
		else:
			# add check-in discord timestamp
			check_in_timeout_epoch = str(int(time.time()) + self.m.cfg['check_in_timeout'])
			embed.add_field(
				name="—",
				value="\n".join([
					self.m.gt("Please react with {ready_emoji} or vote for a map to **check-in**.").format(
						ready_emoji=self.m.check_in.READY_EMOJI
					),
					self.m.gt("React with {not_ready_emoji} to **abort**!").format(
						not_ready_emoji=self.m.check_in.NOT_READY_EMOJI
					),
					self.m.gt("\u1CBC\u1CBC\u1CBC\u1CBC\u1CBC\u1CBC\u1CBC\u1CBC\u1CBC\u1CBC\u1CBC\u1CBC\u1CBC\u1CBC\u1CBC\u1CBC\u1CBC\u1CBC\u1CBC\u1CBC\u1CBC**within:** <t:" + check_in_timeout_epoch + ":R>").format(
						not_ready_emoji=self.m.check_in.NOT_READY_EMOJI
					) + "\n\u200b\nMaps:",
					"\n".join([
						f" \u200b \u200b {self.m.check_in.INT_EMOJIS[i]} \u200b {self.m.check_in.maps[i]}"
						for i in range(len(self.m.check_in.maps))
					])
				]),
				inline=False
			)
		embed.set_footer(**self.footer)

		return embed

	def draft(self, debug=False, jump_url=False):
		embed = Embed(
			colour=Colour(0x8758f5),
			title=self.m.gt("__**{queue}** is now on the draft stage!__").format(
				queue=self.m.queue.name[0].upper()+self.m.queue.name[1:]
			)
		)
		teams_names = [
			f"{t.emoji} \u200b **{t.name}**" +
			(f" \u200b `〈{sum((self.m.ratings[p.id] for p in t))//(len(t) or 1)}〉`" if self.m.ranked else "")
			for t in self.m.teams[:2]
		]
		team_players = [
			" \u200b ".join([
				(f"`{self.m.rank_str(p)}" if self.m.ranked else "`") + f"{get_nick(p)}`" if not debug else f"<@{p.id}>"
				for p in t
			]) if len(t) else self.m.gt("empty")
			for t in self.m.teams[:2]
		]
		embed.add_field(name=teams_names[0], value=" \u200b ❲ \u200b " + team_players[0] + " \u200b ❳", inline=False)
		embed.add_field(name=teams_names[1], value=" \u200b ❲ \u200b " + team_players[1] + " \u200b ❳\n\u200b", inline=False)

		if len(self.m.teams[2]):
			embed.add_field(
				name=self.m.gt("Unpicked:"),
				value="\n".join((
					" \u200b {rank}{name}".format(
						rank=f"`{self.m.rank_str(p)}`" if self.m.ranked else "",
						name=f"`{get_nick(p)}`" if not debug else f"<@{p.id}>"
					)
				) for p in self.m.teams[2]),
				inline=False
			)
		#map in draft

		embed.add_field(name="—", value="", inline=False)

		if len(self.m.maps):
			embed.add_field(
				name=self.m.qc.gt("Map" if len(self.m.maps) == 1 else "Maps"),
				value="".join((f"**{i}**" for i in self.m.maps)),
				inline=True
			)

			if len(self.m.teams[0]) and len(self.m.teams[1]):
				msg = self.m.gt("Pick players with `{prefix}pick @player` command.").format(prefix=self.m.qc.cfg.prefix)
				pick_step = len(self.m.teams[0]) + len(self.m.teams[1]) - 2
				picker_team = self.m.teams[self.m.draft.pick_order[pick_step]] if pick_step < len(self.m.draft.pick_order)-1 else None
				if picker_team:
					msg += "\n" + self.m.gt("{member}'s turn to pick!").format(member=f"<@{picker_team[0].id}>")
			else:
				msg = self.m.gt("Type {cmd} to become a captain and start picking teams.").format(
					cmd=f"`{self.m.qc.cfg.prefix}capfor {'/'.join((team.name.lower() for team in self.m.teams[:2]))}`"
				)

			embed.add_field(name="—", value=msg + "\n\u200b", inline=False)

		if jump_url:
			embed.add_field(name="—", value=jump_url, inline=False)

		embed.set_footer(**self.footer)

		return embed

	def final_message(self):
		show_ranks = bool(self.m.ranked and not self.m.qc.cfg.rating_nicks)
		embed = Embed(
			colour=Colour(0x27b75e),
			title=self.m.qc.gt("__**{queue}** has started!__").format(
				queue=self.m.queue.name[0].upper()+self.m.queue.name[1:]
			)
		)

		if len(self.m.teams[0]) == 1 and len(self.m.teams[1]) == 1:  # 1v1
			p1, p2 = self.m.teams[0][0], self.m.teams[1][0]
			players = " \u200b {player1}{rating1}\n \u200b {player2}{rating2}".format(
				rating1=f" \u200b `〈{self.m.ratings[p1.id]}〉`" if show_ranks else "",
				player1=f"<@{p1.id}>",
				rating2=f" \u200b `〈{self.m.ratings[p2.id]}〉`" if show_ranks else "",
				player2=f"<@{p2.id}>",
			)
			embed.add_field(name=self.m.gt("Players"), value=players, inline=False)
		elif len(self.m.teams[0]):  # team vs team
			teams_names = [
				f"{t.emoji} \u200b **{t.name}**" +
				(f" \u200b `〈{sum((self.m.ratings[p.id] for p in t))//(len(t) or 1)}〉`" if self.m.ranked else "")
				for t in self.m.teams[:2]
			]
			team_players = [
				" \u200b " +
				" \u200b ".join([
					(f"`{self.m.rank_str(p)}`" if show_ranks else "") + f"<@{p.id}>"
					for p in t
				])
				for t in self.m.teams[:2]
			]
			team_players[1] += "\n\u200b"  # Extra empty line
			embed.add_field(name=teams_names[0], value=team_players[0], inline=False)
			embed.add_field(name=teams_names[1], value=team_players[1], inline=False)
			if self.m.ranked or self.m.cfg['pick_captains']:
				embed.add_field(
					name=self.m.gt("Captains"),
					value=" \u200b " + join_and([self.m.teams[0][0].mention, self.m.teams[1][0].mention]),
					inline=False
				)

		else:  # just players list
			embed.add_field(
				name=self.m.gt("Players"),
				value=" \u200b " + " \u200b ".join((m.mention for m in self.m.players)),
				inline=False
			)
			if len(self.m.captains) and len(self.m.players) > 2:
				embed.add_field(
					name=self.m.gt("Captains"),
					value=" \u200b " + join_and([m.mention for m in self.m.captains]),
					inline=False
				)

		if len(self.m.maps):
			embed.add_field(
				name=self.m.qc.gt("Map" if len(self.m.maps) == 1 else "Maps"),
				value="\n".join((f"**{i}**" for i in self.m.maps)),
				inline=True
			)
			print((self.m.maps))
		if self.m.cfg['server']:
			embed.add_field(name=self.m.qc.gt("Server"), value=f"`{self.m.cfg['server']}`", inline=True)

		if self.m.cfg['start_msg']:
			embed.add_field(name="—", value=self.m.cfg['start_msg'] + "\n\u200b", inline=False)

		if self.m.bf2_servers:
			print("^^^^^^^^^^^^^^^^^^^^^^self.m.bf2_servers", [i['ip'] for i in self.m.bf2_servers if 'ip' in i])
			servers_restarted = []
			for server in self.m.bf2_servers:
				if server['restarted']:
					name = server['name'].replace("/bf2pb", "*/*bf2pb")
					servers_restarted.append("**Name:** " +"["+ name +"]"+"(https://joinme.click/g/bf2/"+ server['ip'] +":"+ str(server['bf2port']) +") "+"**IP:** "+"`" + server['hostname'] + "`" + " **PORT:** " + "`" + str(server['bf2port']) + "`")
			restarted_server_string = "\n".join(servers_restarted)
			embed.add_field(
				name=self.m.gt("Use Joinme.click to join one of the servers restarted to " + self.m.maps[0] + ":"),
				value=restarted_server_string,
				inline=False
			)

			# embed.add_field(
				# name=self.m.gt("Servers restarted with the correct map:"),
				# value=" \u200b " + " \u200b " + "\n ".join(("ip: " + server['name'] for server in self.m.bf2_servers if server['restarted'] == True)),
				# value=" \u200b " + " \u200b ".join([server['ip'] for server in bf2_servers]),
				# inline=False
			# )
			# embed.add_field(name="—", value=self.m.cfg['start_msg'] + "\n\u200b", inline=False)
			# for server in bf2_servers:

		if self.m.cfg['show_streamers']:
			if len(streamers := [p for p in self.m.players if isinstance(p.activity, Streaming)]):
				embed.add_field(name=self.m.qc.gt("Player streams"), inline=False, value="\n".join([
					f"{p.mention}: {p.activity.url}" for p in streamers
				]) + "\n\u200b")
		embed.set_footer(**self.footer)

		return embed
