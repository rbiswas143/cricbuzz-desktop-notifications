'''Get commentary for live matches from cricbuzz as desktop notifications'''

import sys
import json
import time
import threading

import requests as req
import notify2 as notify


# Config

APP_NAME = 'CRIX'
REFINT_LIVE = 100
REFINT_STATS = 20
REFINT_NOTIF = 10


# Globals

cached_stats = {}
live_match_ids = []
message_queue = []
all_notifications = {}


# Match Status Class and Notification Formatting

class CricStatus:

	def __init__(self, j):
		self.match = j['match_desc']
		self.team1 = j['team1']['s_name']
		self.team2 = j['team2']['s_name']
		self.teamsDict = {
			j['team1']['id']: self.team1,
			j['team2']['id']: self.team2
		}

		self.score = '0'
		self.wkts = '0'
		self.overs = '0.0'
		self.comm = ''
		self.batting = 'N/A'

		self.new_data = False

	def __setattr__(self, key, value):
		if hasattr(self, 'new_data') and key != 'new_data':
			self.new_data = self.new_data or (self.__dict__[key] != value)
		return super(CricStatus, self).__setattr__(key, value)

	def update(self, j):
		comms = j['comm_lines']
		comm = comms[0]
		if 'score' in comm:
			self.score = comm['score']
		if 'wkts' in comm:
			self.wkts = comm['wkts']
		if 'o_no' in comm:
			self.overs = comm['o_no']
		self.batting = self.teamsDict[j['score']['batting']['id']]
		comm_all = list(map(lambda c: '  {}'.format(c['comm']), filter(lambda c: 'comm' in c, comms[:2])))
		self.comm = "\n".join(comm_all)

	def get_title(self):
		return '{} : {} vs {}'.format(self.match, self.team1, self.team2)

	def get_message(self):
		score = '<b>{}: {}-{} in {}</b>'.format(self.batting, self.score, self.wkts, self.overs)
		return '\n{}\n\n{}'.format(score, self.comm)


# Live match IDs

def get_live_matches():
	cache_path = 'cric-live-cached.json'
	json_url = 'https://www.cricbuzz.com/match-api/livematches.json'
	req_download = req.get(json_url)
	if req_download.status_code == 200:
		json_data = req_download.text
	else:
		print('Invalid page fetch status:', req_download.status_code)
		raise Exception('Failed to fetch live matches')
	j =json.loads(json_data)
	matches = []
	for m_id, m_data in j['matches'].items():
		if m_data['state_title'] == 'Live':
			matches.append(m_id)
	return matches

def refresh_live_matches(refresh_interval=REFINT_LIVE):
	global live_match_ids
	while True:
		try:
			live_match_ids = get_live_matches()
			# print('live_match_ids:', live_match_ids)
		except Exception as e:
			print('Error refreshing live matches', e)
		time.sleep(refresh_interval)


# Match Stats

def get_match_stats(match_id):
	cache_path = 'cric-{}-cached.json'.format(match_id)
	json_url = 'https://www.cricbuzz.com/match-api/{}/commentary.json'.format(match_id)
	req_download = req.get(json_url)
	if req_download.status_code == 200:
		json_data = req_download.text
	else:
		print('Invalid page fetch status:', req_download.status_code)
		raise Exception('Failed to fetch match info for match id "{}"'.format(match_id))
	return json.loads(json_data)


def refresh_match_stats(refresh_interval=REFINT_STATS):
	while True:
		for m_id in live_match_ids[:]:
			try:
				stats_json = get_match_stats(m_id)
				# print('Stats fetched for match id', m_id)
				if m_id not in cached_stats:
					print('New live match id: "{}"'.format(m_id))
					cached_stats[m_id] = CricStatus(stats_json)
				stats = cached_stats[m_id]
				stats.update(stats_json)
			except Exception as e:
				print('Error refreshing match stats for match id "{}"'.format(m_id), e)
		time.sleep(refresh_interval)


# Notifications

def show_notifcation(m_id, stats):
	if m_id not in all_notifications:
		notif = all_notifications[m_id] = notify.Notification(stats.get_title(), stats.get_message())
		notif.timeout = notify.EXPIRES_NEVER
		print('Notification created for match id', m_id)
	else:
		notif = all_notifications[m_id]
		notif.update(stats.get_title(), stats.get_message())
	notif.show()

def refresh_notifications(app_name=APP_NAME, refresh_interval=REFINT_NOTIF):
	notify.init(app_name)
	while True:
		try:
			for m_id, stats in cached_stats.items():
				if not stats.new_data:
					time.sleep(1)
					continue
				else:
					show_notifcation(m_id, stats)
					stats.new_data = False
					time.sleep(refresh_interval)
		except Exception as e:
			print('Error refreshing notifications', e)


# Threads

def start():
	threads = [
		threading.Thread(target=refresh_live_matches, daemon=True),
		threading.Thread(target=refresh_match_stats, daemon=True),
		threading.Thread(target=refresh_notifications, daemon=True)
	]
	for t in threads:
		t.start()
	for t in threads:
		t.join()


if __name__ == '__main__':
	start()