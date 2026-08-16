# -*- coding: utf-8 -*-
from time import time
from itertools import combinations
import random
from discord import DiscordException, Client, Embed

import bot
from bot.main import hardcoded_expire_times
from bot.main import API_KEY
from core.utils import find, get, iter_to_dict, join_and, get_nick
from core.client import dc

from .check_in import CheckIn
from .draft import Draft
from .embeds import Embeds


import socket
import hashlib
import re
import requests

import threading
from time import sleep
import asyncio

# global bf2_servers
from bot.main import bf2_servers
import json
import os
from bot.main import bf2top_fetch

class Match:

	API_KEY = API_KEY
	INIT = 0
	CHECK_IN = 1
	DRAFT = 2
	WAITING_REPORT = 3

	TEAM_EMOJIS = [
		":fox:", ":wolf:", ":dog:", ":bear:", ":panda_face:", ":tiger:", ":lion:", ":pig:", ":octopus:", ":boar:",
		":scorpion:", ":crab:", ":eagle:", ":shark:", ":bat:", ":rhino:", ":dragon_face:", ":deer:"
	]

	default_cfg = dict(
		teams=None, team_names=['Alpha', 'Beta'], team_emojis=None, ranked=False,
		team_size=1, pick_captains="no captains", captains_role_id=None, pick_teams="draft",
		pick_order=None, maps=[], vote_maps=0, map_count=0, check_in_timeout=0,
		check_in_discard=True, match_lifetime=3*60*60, start_msg=None, server=None, show_streamers=True
	)

	class Team(list):
		""" Team is basically a set of member objects, but we need it ordered so list is used """

		def __init__(self, name=None, emoji=None, players=None, idx=-1):
			super().__init__(players or [])
			self.name = name
			self.emoji = emoji
			self.draw_flag = False  # 1 - wants draw; 2 - wants cancel
			self.idx = idx

		def set(self, players):
			self.clear()
			self.extend(players)

		def add(self, p):
			if p not in self:
				self.append(p)

		def rem(self, p):
			if p in self:
				self.remove(p)

	@classmethod
	async def new(cls, queue, qc, players, **kwargs):
		# Create the Match object
		ratings = {p['user_id']: p['rating'] for p in await qc.rating.get_players((p.id for p in players))}
		bot.last_match_id += 1
		match = cls(bot.last_match_id, queue, qc, players, ratings, **kwargs)
		# Prepare the Match object
		match.maps = match.random_maps(match.cfg['maps'], match.cfg['map_count'], queue.last_maps)
		match.init_captains(match.cfg['pick_captains'], match.cfg['captains_role_id'])
		match.init_teams(match.cfg['pick_teams'])
		if match.ranked:
			match.states.append(match.WAITING_REPORT)
		bot.active_matches.append(match)

	@classmethod
	async def fake_ranked_match(cls, queue, qc, winners, losers, draw=False, **kwargs):
		players = winners + losers
		if len(set(players)) != len(players):
			raise bot.Exc.ValueError("Players list can not contains duplicates.")
		ratings = {p['user_id']: p['rating'] for p in await qc.rating.get_players((p.id for p in players))}
		bot.last_match_id += 1
		match = cls(bot.last_match_id, queue, qc, players, ratings, pick_teams="premade", **kwargs)
		match.teams[0].set(winners)
		match.teams[1].set(losers)
		match.winner = None if draw else 0
		await bot.stats.register_match_ranked(match)

	def serialize(self):
		return dict(
			match_id=self.id,
			queue_id=self.queue.id,
			channel_id=self.qc.id,
			cfg=self.cfg,
			players=[p.id for p in self.players if p],
			teams=[[p.id for p in team if p] for team in self.teams],
			maps=self.maps,
			state=self.state,
			states=self.states,
			ready_players=[p.id for p in self.check_in.ready_players if p]
		)

	@classmethod
	async def from_json(cls, queue, qc, data):
		# Prepare discord objects
		data['players'] = [qc.channel.guild.get_member(user_id) for user_id in data['players']]
		if None in data['players']:
			await qc.error(f"Unable to load match {data['match_id']}, error fetching guild members.")
			return

		# Fill data with discord objects
		for i in range(len(data['teams'])):
			data['teams'][i] = [get(data['players'], id=user_id) for user_id in data['teams'][i]]
		data['ready_players'] = [get(data['players'], id=user_id) for user_id in data['ready_players']]

		# Create the Match object
		ratings = {p['user_id']: p['rating'] for p in await qc.rating.get_players((p.id for p in data['players']))}
		bot.last_match_id += 1
		match = cls(bot.last_match_id, queue, qc, data['players'], ratings, **data['cfg'])

		# Set state data
		for i in range(len(match.teams)):
			match.teams[i].set(data['teams'][i])
		match.check_in.ready_players = set(data['ready_players'])
		match.maps = data['maps']
		match.state = data['state']
		match.states = data['states']
		if match.state == match.CHECK_IN:
			await match.check_in.start()  # Spawn a new check_in message

		bot.active_matches.append(match)

	def __init__(self, match_id, queue, qc, players, ratings, **cfg):

		# Set parent objects and shorthands
		self.queue = queue
		self.qc = qc
		self.send = qc.channel.send
		self.gt = qc.gt

		# Set configuration variables
		cfg = {k: v for k, v in cfg.items() if v is not None}  # filter kwargs for notnull values
		self.cfg = self.default_cfg.copy()
		self.cfg.update(cfg)

		# Set working objects
		self.id = match_id
		self.ranked = self.cfg['ranked'] and self.cfg['pick_teams'] != 'no teams'
		self.players = list(players)
		self.ratings = ratings
		self.winner = None
		self.scores = [0, 0]

		team_names = self.cfg['team_names']
		team_emojis = self.cfg['team_emojis'] or random.sample(self.TEAM_EMOJIS, 2)
		self.teams = [
			self.Team(name=team_names[0], emoji=team_emojis[0], idx=0),
			self.Team(name=team_names[1], emoji=team_emojis[1], idx=1),
			self.Team(name="unpicked", emoji="📋", idx=-1)
		]

		self.captains = []
		self.states = []
		self.maps = []
		self.lifetime = self.cfg['match_lifetime']
		self.start_time = int(time())
		self.state = self.INIT

		self.check_in_timeout = self.cfg['check_in_timeout']
		self.bf2_servers = bf2_servers

		# Init self sections
		self.check_in = CheckIn(self, self.cfg['check_in_timeout'])
		self.draft = Draft(self, self.cfg['pick_order'], self.cfg['captains_role_id'])
		self.embeds = Embeds(self)

	@staticmethod
	def random_maps(maps, map_count, last_maps=None):
		for last_map in (last_maps or [])[::-1]:
			if last_map in maps and map_count < len(maps):
				maps.remove(last_map)

		return random.sample(maps, min(map_count, len(maps)))

	def sort_players(self, players):
		""" sort given list of members by captains role and rating """
		return sorted(
			players,
			key=lambda p: [self.cfg['captains_role_id'] in [role.id for role in p.roles], self.ratings[p.id]],
			reverse=True
		)

	def init_captains(self, pick_captains, captains_role_id):
		if pick_captains == "by role and rating":
			self.captains = self.sort_players(self.players)[:2]
		elif pick_captains == "fair pairs":
			candidates = sorted(self.players, key=lambda p: [self.ratings[p.id]], reverse=True)
			i = random.randrange(len(candidates) - 1)
			self.captains = [candidates[i], candidates[i + 1]]
		elif pick_captains == "random":
			self.captains = random.sample(self.players, 2)
		elif pick_captains == "random with role preference":
			rand = random.sample(self.players, len(self.players))
			self.captains = sorted(
				rand, key=lambda p: self.cfg['captains_role_id'] in [role.id for role in p.roles], reverse=True
			)[:2]

	def init_teams(self, pick_teams):
		if pick_teams == "draft":
			self.teams[0].set(self.captains[:1])
			self.teams[1].set(self.captains[1:])
			self.teams[2].set([p for p in self.players if p not in self.captains])
		elif pick_teams == "matchmaking":
			team_len = min(self.cfg['team_size'], int(len(self.players)/2))
			best_rating = sum(self.ratings.values())/2
			best_team = min(
				combinations(self.players, team_len),
				key=lambda team: abs(sum([self.ratings[m.id] for m in team])-best_rating)
			)
			self.teams[0].set(self.sort_players(
				best_team[:self.cfg['team_size']]
			))
			self.teams[1].set(self.sort_players(
				[p for p in self.players if p not in best_team][:self.cfg['team_size']]
			))
			self.teams[2].set([p for p in self.players if p not in [*self.teams[0], *self.teams[1]]])
		elif pick_teams == "random teams":
			self.teams[0].set(random.sample(self.players, min(len(self.players)//2, self.cfg['team_size'])))
			self.teams[1].set([p for p in self.players if p not in self.teams[0]][:self.cfg['team_size']])
			self.teams[2].set([p for p in self.players if p not in [*self.teams[0], *self.teams[1]]])

	async def think(self, frame_time):
		if self.state == self.INIT:
			await self.next_state()

		elif self.state == self.CHECK_IN:
			await self.check_in.think(frame_time)

		elif frame_time > self.lifetime + self.start_time:
			try:
				await self.qc.error(self.gt("Match {queue} ({id}) has timed out.").format(
					queue=self.queue.name,
					id=self.id
				))
			except DiscordException:
				pass
			await self.cancel()

	async def next_state(self):
		if len(self.states):
			self.state = self.states.pop(0)
			if self.state == self.CHECK_IN:
				await self.check_in.start()
			elif self.state == self.DRAFT:
				await self.draft.start()
			elif self.state == self.WAITING_REPORT:
				await self.start_waiting_report()
		else:
			if self.state != self.WAITING_REPORT:
				await self.final_message()
			await self.finish_match()

	def rank_str(self, member):
		return self.qc.rating_rank(self.ratings[member.id])['rank']

	async def start_waiting_report(self):
		# remove never picked players from the match
		if len(self.teams[2]):
			for p in self.teams[2]:
				self.players.remove(p)
			await self.send(self.gt("{players} were removed from the match.").format(
				players=join_and([m.mention for m in self.teams[2]])
			))
			unpicked = list(self.teams[2])
			self.teams[2].clear()
			await self.final_message()
			await self.queue.revert([], unpicked)
		else:
			await self.final_message()

	async def report_loss(self, member, draw_flag):
		if self.state != self.WAITING_REPORT:
			raise bot.Exc.MatchStateError(self.gt("The match must be on the waiting report stage."))

		team = find(lambda team: member in team[:1], self.teams[:2])
		if team is None:
			raise bot.Exc.PermissionError(self.gt("You must be a team captain to report a loss or draw."))

		enemy_team = self.teams[1-team.idx]
		if draw_flag and not enemy_team.draw_flag == draw_flag:
			team.draw_flag = draw_flag
			await self.qc.channel.send(
				self.gt(
					"{self} is calling a draw, waiting for {enemy} to type `{prefix}rd`." if draw_flag == 1 else
					"{self} offers to cancel the match, waiting for {enemy} to type `{prefix}rc`."
				).format(
					self=member.mention,
					enemy=enemy_team[0].mention,
					prefix=self.qc.cfg.prefix
				)
			)
			return

		if draw_flag == 2:
			await self.cancel()
			return

		elif draw_flag == 1:
			self.winner = None
		else:
			self.winner = enemy_team.idx
			self.scores[self.winner] = 1
		await self.finish_match()

	async def report_win(self, team_name):  # version for admins/mods
		if self.state != self.WAITING_REPORT:
			raise bot.Exc.MatchStateError(self.gt("The match must be on the waiting report stage."))

		team_name = team_name.lower()
		if team_name == "draw":
			self.winner = None
		elif (team := find(lambda t: t.name.lower() == team_name, self.teams[:2])) is not None:
			self.winner = team.idx
			self.scores[self.winner] = 1
		else:
			raise bot.Exc.SyntaxError(self.gt("Specified team name not found."))

		await self.finish_match()

	async def report_scores(self, scores):
		if self.state != self.WAITING_REPORT:
			raise bot.Exc.MatchStateError(self.gt("The match must be on the waiting report stage."))

		if scores[0] > scores[1]:
			self.winner = 0
		elif scores[1] > scores[0]:
			self.winner = 1
		else:
			self.winner = None

		self.scores = scores
		await self.finish_match()

	async def print_rating_results(self, before, after):
		msg = "```markdown\n"
		msg += f"{self.queue.name.capitalize()}({self.id}) results\n"
		msg += "-------------"

		if self.winner is not None:
			winners, losers = self.teams[self.winner], self.teams[abs(self.winner-1)]
		else:
			winners, losers = self.teams[:2]

		if len(winners) == 1 and len(losers) == 1:
			p = winners[0]
			msg += f"\n1. {get_nick(p)} {before[p.id]['rating']} ⟼ {after[p.id]['rating']}"
			p = losers[0]
			msg += f"\n2. {get_nick(p)} {before[p.id]['rating']} ⟼ {after[p.id]['rating']}"
		else:
			n = 0
			for team in (winners, losers):
				avg_bf = int(sum((before[p.id]['rating'] for p in team))/len(team))
				avg_af = int(sum((after[p.id]['rating'] for p in team))/len(team))
				msg += f"\n{n}. {team.name} {avg_bf} ⟼ {avg_af}\n"
				msg += "\n".join(
					(f"> {get_nick(p)} {before[p.id]['rating']} ⟼ {after[p.id]['rating']}" for p in team)
				)
				n += 1
		msg += "```"
		await self.qc.channel.send(msg)

	async def final_message(self):
		#  Embed message with teams
		await self.qc.channel.send("join one of the match servers and ts.", delete_after=10.0)
		try:
			bf2top_fetch.load_servers()  # Reload data
			for server in bf2top_fetch.get_bf2_servers():
				print(server)
			self.restart_bf2_servers(self.maps)
			await self.qc.channel.send(embed=self.embeds.final_message())
			print(self.maps)
		except DiscordException:
			pass

	async def finish_match(self):
		bot.active_matches.remove(self)
		self.queue.last_maps += self.maps
		self.queue.last_maps = self.queue.last_maps[-len(self.maps)*self.queue.cfg.map_cooldown:]

		if self.ranked:
			await bot.stats.register_match_ranked(self)
		else:
			await bot.stats.register_match_unranked(self)

	def print(self):
		return f"> *({self.id})* **{self.queue.name}** | `{join_and([get_nick(p) for p in self.players])}`"

	async def cancel(self):
		if self.check_in.message and self.check_in.message.id in bot.waiting_reactions.keys():
			bot.waiting_reactions.pop(self.check_in.message.id)
		try:
			await self.qc.channel.send(
				self.gt("{players} your match has been canceled.").format(players=join_and([p.mention for p in self.players]))
			)
		except DiscordException:
			pass
		bot.active_matches.remove(self)
		
	def init_web_admin(self, server):
		host = server["ip"]
		port = server["port"]
		password = server["rcon_password"]

		# print(f"connecting to {host}:{port}")

		wa_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		wa_client.settimeout(2)
		wa_client.connect((host, port))
		
		print("connected to rcon", server["ip"])

		def handle_login(data):
			seed = data.split("### Digest seed: ")[-1].strip()
			# print(f"authenticating with seed {seed}")
			wa_client.send(f"login {hashlib.md5(seed.encode() + password.encode()).hexdigest()}\n".encode())

		while True:
			chunk = wa_client.recv(1024).decode()
			if not chunk:
				# raise RuntimeError("Authentication failed - connection closed without successful authentication")
				break
			if "### Digest seed: " in chunk:
				handle_login(chunk)
			if "Authentication successful" in chunk:
				# print("authenticated")
				break
		# print("disconnected from rcon", server["ip"])
		return wa_client
		
	def get_user_list(self, rcon):
		user_match = re.compile(r'Id: \s?([0-9]+)\s+-\s+(.*)\s+is remote ip: ([0-9.]+):[0-9]+\s+->\s+CD-key hash: ([a-z0-9]+)')
		user_list = []
		rcon.send("exec admin.listPlayers\n".encode())
		data = rcon.recv(1024).decode()
		match = user_match.search(data)
		while match:
			user_list.append({
				"id": match.group(1),
				"name": match.group(2),
				"ip": match.group(3),
				"cdkey": match.group(4),
			})
			match = user_match.search(data, pos=match.end())
		return user_list

	def restart_bf2server_rcon(self, server):
	# BF2cc required to be installed on server
		user_match = re.compile(r'Id: \s?([0-9]+)\s+-\s+(.*)\s+is remote ip: ([0-9.]+):[0-9]+\s+->\s+CD-key hash: ([a-z0-9]+)')
		user_list = []
		rcon = self.init_web_admin(server)
		rcon.send("exec quit\n".encode())
		data = rcon.recv(1024).decode()
		print("_____________restart_bf2server_rcon___________________________",  data)
		return data


	def old2_check_bf2_players(self, server):
		server = server
		# global bf2_servers
		# for server in bf2_servers:
		rcon = self.init_web_admin(server)
		global user_list
		try:
			user_list = self.get_user_list(rcon)
			user_list = (user_list, True)
			rcon.close()
			return user_list
		except:
			user_list = (0, False)
			rcon.close()
			return user_list
#		print(f"List of players for server {server['hostname']}:{server['port']}:")
#		for user in user_list:
#			print(f"{user['id']} - {user['name']} - {user['ip']}:{user['cdkey']}")

		#return user_list
		#rcon.close()
		
	def old1_check_bf2_players(self, server):
		server = server
		# global bf2_servers
		# for server in bf2_servers:
		rcon = self.init_web_admin(server)
		global user_list
		user_list = self.get_user_list(rcon)
#		print(f"List of players for server {server['hostname']}:{server['port']}:")
#		for user in user_list:
#			print(f"{user['id']} - {user['name']} - {user['ip']}:{user['cdkey']}")

		return user_list
		rcon.close()
		
	# import json
	# import re
	# import os

	def validate_user_list(self, user_list):
		ip_regex = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')

		validated_list = []
		invalid_data = []

		for user_data in user_list:
			# Additional validation for IP and CD key
			if ip_regex.match(user_data["ip"]) and len(user_data["cdkey"]) == 32:
				validated_list.append(user_data)
			else:
				print(f"Invalid data detected: {user_data}")
				print(f"IP: {user_data['ip']}, CD Key Length: {len(user_data['cdkey'])}")
				invalid_data.append(user_data)

		if invalid_data:
			self.write_log_file(invalid_data)

		return validated_list

	def write_log_file(self, data):
		log_file_path = "pubobot_invalid_user_data.log"

		# Create the log file if it doesn't exist
		if not os.path.exists(log_file_path):
			with open(log_file_path, "w"):
				pass

		with open(log_file_path, "a") as log_file:
			for item in data:
				log_file.write(json.dumps(item) + "\n")

		print(f"Invalid user data written to log file: {log_file_path}")

		
	def check_bf2_players(self, server):
		rcon1 = self.init_web_admin(server)
		rcon2 = self.init_web_admin(server)

		try:
			# First RCON check
			user_list1 = self.get_user_list(rcon1)

			# Second RCON check
			user_list2 = self.get_user_list(rcon2)

			# Validate IP and CD key for user_list1
			validated_user_list1 = self.validate_user_list(user_list1)
			# Validate list not empty
			if user_list1 and user_list2:
				# Compare the user_lists
				if user_list1 == user_list2 and validated_user_list1:
					print("User lists match, and validation passed.")
					# Continue with your logic using user_list1 or user_list2
					return user_list1
				else:
					print("User lists do not match or validation failed.")
					# Handle the case where user lists do not match or validation fails
					return None
			else:
				return user_list1

		except Exception as e:
			print(f"Error during RCON checks: {e}")
			# Handle the error as needed

		finally:
			# Close the RCON connections
			if 'rcon1' in locals():
				rcon1.close()
			if 'rcon2' in locals():
				rcon2.close()

		return None
	
	def restart_bf2_servers(self, map_name):
		print("_____________bf2.servers___________________________",  [i['hostname'] for i in self.bf2_servers if 'hostname' in i], id(self.bf2_servers))
#		self.bf2_servers = bf2_servers
		if not map_name:
			map_name = "Gulf Of Oman"
		for server in self.bf2_servers:
			server['restarted'] = False
			try:
				user_list = self.check_bf2_players(server)

				# print(len(user_list), user_list, self.qc.id, dc.get_channel(self.qc.id), dc.get_channel(self.qc.id).name)
				print("len(user_list):", len(user_list), "user_list:", user_list, "self.qc.id:", self.qc.id, "dc.get_channel(self.qc.id):", dc.get_channel(self.qc.id), "dc.get_channel(self.qc.id).name:", dc.get_channel(self.qc.id).name)

				# print(server['hostname'])

				# if len(user_list[0]) <= 3 and user_list[1] == True:
				if len(user_list) <= 3:
					if self.qc.id in [502231263827197952 , 1045376644422045706]:
						serverName = server['name'] + " 8v8"
						print(server['hostname'], len(user_list), user_list,  map_name[0], serverName)
						#url = f"http://{server['hostname']}:{server['jsport']}/restart_vehicles"
						url = f"https://api.bf2.top/servers/{server['hostname']}/restart" #via bf2.top
						headers = {'Content-Type': 'application/json', 'X-API-KEY': API_KEY} #bf2.top
#						payload_dict = {"apiKey": "dIC", "mapName": map_name[0], "serverName": server_name}
#						payload = json.dumps(payload_dict)
#						payload = '{"apiKey": "dIC", "mapName": "'+ map_name[0] +'", "serverName": "'+ serverName +'"}' direct to bf2wa
						payload = '{"mode": "vehicles", "mapName": "'+ map_name[0] +'", "serverName": "'+ serverName +'", "admins": "all", "pubobotMatchId": "'+ str(self.id) +'"}' #via bf2.top
						response = requests.post(url, headers=headers, data=payload, timeout=10)
						response.raise_for_status()
						server['restarted'] = True
						print(f"----------------------------Restarting server {server['hostname']} {server['restarted']} as it has 2 players or less {response}")
					# else:
						# print(f"Not restarting server {server['hostname']} as it has 2 players or more")
						# print(server['hostname'], len(user_list), user_list,  map_name[0])
					else:
						if self.qc.id == 1035999895968030800:
							# print(f"Restarting server BF2 servers",  map_name[0])
							try:
								serverName
							except:
								serverName = server['name'] + " 1v1"
						if self.qc.id == 738113190507839598:
							serverName = server['name'] # + " 2v2"
						elif self.qc.id == 597415520337133571:
							serverName = server['name'] #+ " 4v4"
						elif self.qc.id == 597428419617095680:
							serverName = server['name'] #+ " 5v5"
						else:
							serverName = server['name'] + " 1v1"
						# print(f"Restarting server BF2 servers",  map_name[0])
						# print(server['hostname'], len(user_list), user_list,  map_name[0], serverName)
						#url = f"http://{server['hostname']}:{server['jsport']}/restart"
						url = f"https://api.bf2.top/servers/{server['hostname']}/restart" #via bf2.top
						headers = {'Content-Type': 'application/json', 'X-API-KEY': API-KEY} #via bf2.top
						#payload_dict = {"apiKey": "dIC", "mapName": map_name[0], "serverName": server_name}
						#payload = json.dumps(payload_dict)
						payload = '{"mode": "infantry", "mapName": "'+ map_name[0] +'", "serverName": "'+ serverName +'", "admins": "all", "pubobotMatchId": "'+ str(self.id) +'"}'
						response = requests.post(url, headers=headers, data=payload, timeout=5)
						print("Response text:", response.text)
						response.raise_for_status()
						server['restarted'] = True
						print(f"-----------------------------Restarting server: {server['hostname']} with name: {serverName} as it has 2 players or less {response}")
				else:
					print(f"Not restarting server {server['hostname']} as it has 2 players or more")
					print(server['hostname'], len(user_list), user_list,  map_name[0])
			except (requests.RequestException, requests.HTTPError) as e:
				# rcon_message = self.restart_bf2server_rcon(server)
				# if "*** Game will exit! ***" in rcon_message:
					# server['restarted'] = True
				# self.changemap_bf2server_rcon(server)
				print("_____________threading map_name___________________________",  map_name[0], map_name)

				# thread = threading.Thread(target=self.changemap_bf2server_rcon, args=(server,map_name,))
				# thread = threading.Thread(target=between_callback, args=(server,map_name,))
				loop = asyncio.get_running_loop()
				thread = threading.Thread(target=asyncio.run, args=(self.changemap_bf2server_rcon(loop,server,map_name,),))
				thread.start()

				print("error connecting with rcon to", server, e)

				# Only print response details if available
				if hasattr(e, "response") and e.response is not None:
					print(f"Response Status: {e.response.status_code}")
					print(f"Response Body: {e.response.text}")
				# print(e)
				#break
			except Exception as e:
				print("An exception occurred:")
				print(f"Type: {type(e)}")       # Type of the exception
				print(f"Args: {e.args}")        # Arguments passed to the exception
				print(f"Message: {str(e)}")     # Exception message
				# traceback.print_exc()           # Complete traceback

	# async def some_callback(self, args):
		# await some_function()

	# def between_callback(self, args):
		# loop = asyncio.new_event_loop()
		# asyncio.set_event_loop(loop)

		# loop.run_until_complete(changemap_bf2server_rcon(args))
		# loop.close()

	async def changemap_bf2server_rcon(self, loop, server, match_map_name):
	# BF2cc required to be installed on server
		rcon = self.init_web_admin(server)
		rcon.send("exec quit\n".encode())
		sleep(15)
		rcon = self.init_web_admin(server)
		rcon.send("exec maplist.list\n".encode())
		data = rcon.recv(1024).decode()

		maps = data.split('\n')[:-1]  # split the response into a list of maps

		map_dict = {}  # create an empty dictionary to store the formatted maps

		for map in maps:
			map_parts = map.split(': ')
			map_name = map_parts[1].replace(' gpm_cq','').replace(" 16",'').replace('"','').replace('_',' ').title()
			map_dict[map_name] = map_parts[0]  # add the map to the dictionary with the formatted name as the key

		# print("_____________restart_bf2server_rcon___________________________",  data, map_dict, match_map_name[0])
		print("_____________restart_bf2server_rcon___________________________",  map_dict, match_map_name[0])
		print("_____________restart_bf2server_rcon___________________________",  match_map_name[0], match_map_name)
		next_level_id = str(map_dict[match_map_name[0]])
		rcon.send(("exec admin.setNextLevel "+ next_level_id + "\n").encode())
		sleep(1)
		rcon.send("exec admin.runNextLevel\n".encode())
		asyncio.run_coroutine_threadsafe(self.discordmsg_bf2server_rcon(server, match_map_name), loop)
		return data
	
	async def discordmsg_bf2server_rcon(self, server, match_map_name):
		try:
			name = server['name'].replace("/bf2pb", "*/*bf2pb")
			# embed = Embed(description="Also restarted and changed map to **"+ match_map_name[0] +"**: ["+ name +"]"+"(https://joinme.click/g/bf2/"+ server['ip'] +":"+ str(server['bf2port']) +") "+"**IP:** "+"`" + server['hostname'] + "`" + " **PORT:** " + "`" + str(server['bf2port']) + "`")
			# await self.qc.channel.send(embed=embed)
			message = "Also restarted and changed map to **"+ match_map_name[0] +"**: ["+ name +"]"+"(https://joinme.click/g/bf2/"+ server['ip'] +":"+ str(server['bf2port']) +") "+"**IP:** "+"`" + server['hostname'] + "`" + " **PORT:** " + "`" + str(server['bf2port']) + "`"
			message = await self.qc.channel.send(message)
			await message.edit(suppress=True)
		except DiscordException:
			pass

