#!/usr/bin/env python

import requests
import config
import datetime
import praw
import sqlite3
import re

# The subreddit on which to run the bot
SUBREDDIT = 'leagueoflegends'

# Riot API url for match stats
RIOT_MATCH_API = 'https://na.api.pvp.net/api/lol/%s/v2.2/match/%s?api_key=%s'

# Static champion data url
CHAMPION_DATA = 'https://global.api.pvp.net/api/lol/static-data/%s/v1.2/champion?api_key=%s'

# Summoner spells data url
SUMMONER_SPELLS_DATA = 'https://global.api.pvp.net/api/lol/static-data/%s/v1.2/summoner-spell?api_key=%s'

# Mapping of champion and summoner spell names with IDs
CHAMPION_MAP = {}
SUMMONER_MAP = {}


# Match data structure
class Match:
    def __init__(self, region, match_id):
        """
        Initiates match object with a bunch of data for the given match id
        """
        self.match_id = match_id
        self.region = region
        endpoint = RIOT_MATCH_API % (region.lower(), match_id, config.riot_api_key)
        # print endpoint
        response = requests.get(endpoint)
        response = response.json()
        # do some stuff with the data
        players = response['participants']
        team1 = []
        team2 = []
        # sort the players into their teams
        for p in players:
            player = Player(p)
            if player.team_id == 100:
                team1.append(player)
            else:
                team2.append(player)
        self.team1 = team1
        self.team2 = team2
        self.team1kills = get_team_kills(team1)
        self.team2kills = get_team_kills(team2)
        self.match_mode = response['matchMode']
        teams = response['teams']
        for t in teams:
            if t['teamId'] == 100:
                if t['winner']:
                    self.winner = 'Team 1'
                    break
                else:
                    self.winner = 'Team 2'
                    break
        if self.winner == 'Team 1':
            self.winnerkills = self.team1kills
            self.loserkills = self.team2kills
        else:
            self.winnerkills = self.team2kills
            self.loserkills = self.team1kills
        duration = response['matchDuration']
        hours, remainder = divmod(duration, 3600)
        minutes, seconds = divmod(remainder, 60)
        self.match_duration = '%d:%02d:%02d' % (hours, minutes, seconds)
        self.match_creation = datetime.datetime.fromtimestamp(response['matchCreation']/1000.0)
        self.queue_type = response['queueType']

    # Formats the match data for posting to reddit, in one giant string
    def reddit_format(self):
        thestring = ("***Winner: {match.winner}***\n"
                     "\n"
                     "{match.winnerkills} - {match.loserkills}\n"
                     "\n"
                     "***Team 1***\n"
                     "\n"
                     "Champion | Level | Name | KDA | Gold | CS\n"
                     ":---:|---|----|----|----|----\n"
                     "[](/{match.team1[0].champion_lower}) | {match.team1[0].level} | {match.team1[0].champion} | {match.team1[0].kda} | {match.team1[0].gold} | {match.team1[0].minions_killed}\n"
                     "[](/{match.team1[1].champion_lower}) | {match.team1[1].level} | {match.team1[1].champion} | {match.team1[1].kda} | {match.team1[1].gold} | {match.team1[1].minions_killed}\n"
                     "[](/{match.team1[2].champion_lower}) | {match.team1[2].level} | {match.team1[2].champion} | {match.team1[2].kda} | {match.team1[2].gold} | {match.team1[2].minions_killed}\n"
                     "[](/{match.team1[3].champion_lower}) | {match.team1[3].level} | {match.team1[3].champion} | {match.team1[3].kda} | {match.team1[3].gold} | {match.team1[3].minions_killed}\n"
                     "[](/{match.team1[4].champion_lower}) | {match.team1[4].level} | {match.team1[4].champion} | {match.team1[4].kda} | {match.team1[4].gold} | {match.team1[4].minions_killed}\n"
                     "\n"
                     "***Team 2***\n"
                     "\n"
                     "Champion | Level | Name | KDA | Gold | CS\n"
                     ":---:|---|----|----|----|----\n"
                     "[](/{match.team2[0].champion_lower}) | {match.team2[0].level} | {match.team2[0].champion} | {match.team2[0].kda} | {match.team2[0].gold} | {match.team2[0].minions_killed}\n"
                     "[](/{match.team2[1].champion_lower}) | {match.team2[1].level} | {match.team2[1].champion} | {match.team2[1].kda} | {match.team2[1].gold} | {match.team2[1].minions_killed}\n"
                     "[](/{match.team2[2].champion_lower}) | {match.team2[2].level} | {match.team2[2].champion} | {match.team2[2].kda} | {match.team2[2].gold} | {match.team2[2].minions_killed}\n"
                     "[](/{match.team2[3].champion_lower}) | {match.team2[3].level} | {match.team2[3].champion} | {match.team2[3].kda} | {match.team2[3].gold} | {match.team2[3].minions_killed}\n"
                     "[](/{match.team2[4].champion_lower}) | {match.team2[4].level} | {match.team2[4].champion} | {match.team2[4].kda} | {match.team2[4].gold} | {match.team2[4].minions_killed}\n").format(match=self)
        return thestring


class Player:
    def __init__(self, participant_object):
        """
        Initiates player with info from 'participants' list in the match api response
        """
        #self.summoner_spell1 = SUMMONER_MAP[participant_object['spell1Id']]
        #self.summoner_spell2 = SUMMONER_MAP[participant_object['spell2Id']]
        self.champion = CHAMPION_MAP[participant_object['championId']]
        self.champion_lower = ''.join(c for c in self.champion.lower() if c.isalnum())
        self.team_id = participant_object['teamId']
        stats = participant_object['stats']
        self.level = stats['champLevel']
        self.kills = stats['kills']
        self.deaths = stats['deaths']
        self.assists = stats['assists']
        self.gold = stats['goldEarned']
        self.minions_killed = stats['minionsKilled']
        self.kda = '%d/%d/%d' % (self.kills, self.deaths, self.assists)


# def parse_arguments():
#     parser = argparse.ArgumentParser()
#     parser.add_argument('-m', '--match')
#     parser.add_argument('-r', '--region')
#     args = parser.parse_args()
#     return args.region, args.match


def get_champion_map(region):
    """
    creates mapping of champion id to name
    """
    champion_data_url = CHAMPION_DATA % (region, config.riot_api_key)
    champions = requests.get(champion_data_url).json()
    champions = champions['data']
    for c in champions.iteritems():
        CHAMPION_MAP[c[1]['id']] = c[1]['name']


def get_summoner_map(region):
    summoner_spells_url = SUMMONER_SPELLS_DATA % (region, config.riot_api_key)
    summoners = requests.get(summoner_spells_url).json()
    summoners = summoners['data']
    for s in summoners.iteritems():
        SUMMONER_MAP[s[1]['id']] = s[1]['name']


# Gets total number of kills on the team
def get_team_kills(player_list):
    total = 0
    for p in player_list:
        total += p.kills
    return total


# For logging purposes
def log(string):
    print '[' + str(datetime.datetime.now()) + '] ' + string


def main():
    region = 'na'
    # get_summoner_map(region)

    # connect to database to make sure we don't reply to the same comment twice
    db = sqlite3.connect('comments.db')
    cursor = db.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS comments(ID TEXT)')
    db.commit()

    # log into reddit, get comments, etc
    user_agent = "LoL Match Stats by /u/Moomoomoo1"
    r = praw.Reddit(user_agent=user_agent)
    r.login(config.bot_username, config.bot_password)
    sub = r.get_subreddit(SUBREDDIT)
    log('getting comments...')
    comments = sub.get_comments(limit=100)
    for c in comments:
        comment_id = c.id
        cursor.execute('SELECT * FROM comments WHERE ID=?', [comment_id])
        if cursor.fetchone():
            log('already replied to comment ' + str(comment_id))
            continue  # we've already done this comment
        comment_body = c.body.lower()
        m = re.search(r'\bmatch (\d{10})\b', comment_body)
        if m:
            log('replying to comment ' + str(comment_id))
            match_id = m.group(1)
            if not CHAMPION_MAP:
                get_champion_map(region)
            match = Match(region, match_id)
            if '5x5' not in match.queue_type:
                log('Match format not supported')
                continue
            try:
                c.reply(match.reddit_format())
            except praw.errors.RateLimitExceeded as error:
                log("Rate limit exceeded, please wait %d seconds" % error.sleep_time)
                exit(1)
            cursor.execute('INSERT INTO comments VALUES(?)', [comment_id])
            db.commit()



if __name__ == '__main__':
    main()