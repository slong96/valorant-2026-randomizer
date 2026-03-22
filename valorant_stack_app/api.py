import requests
import random
import threading
from datetime import timedelta

from django.utils import timezone

from .models import Agent


SYNC_MAX_AGE_HOURS = 24
SYNC_LOCK = threading.Lock()


def _candidate_agents_for_role(available_agents, preferred_role):
    if not preferred_role:
        return list(available_agents)

    return [agent for agent in available_agents if agent['role'] == preferred_role]


def _build_unique_assignments(players, available_agents):
    player_candidates = {}
    for player in players:
        candidates = _candidate_agents_for_role(available_agents, player.get('preferredRole', ''))
        if not candidates:
            return None
        player_candidates[player['id']] = candidates

    # Assign constrained players first to reduce dead ends.
    ordered_players = sorted(players, key=lambda player: len(player_candidates[player['id']]))
    assignments_by_player = {}
    used_agent_names = set()

    def backtrack(index):
        if index == len(ordered_players):
            return True

        player = ordered_players[index]
        player_id = player['id']
        options = [agent for agent in player_candidates[player_id] if agent['name'] not in used_agent_names]
        random.shuffle(options)

        for agent in options:
            assignments_by_player[player_id] = agent
            used_agent_names.add(agent['name'])

            if backtrack(index + 1):
                return True

            used_agent_names.remove(agent['name'])
            del assignments_by_player[player_id]

        return False

    if not backtrack(0):
        return None

    return [
        {
            'id': player['id'],
            'playerName': player['name'],
            'agent': {
                'name': assignments_by_player[player['id']]['name'],
                'role': assignments_by_player[player['id']]['role'],
                'displayIcon': assignments_by_player[player['id']]['display_icon'],
            },
        }
        for player in players
    ]

def get_agent_data():
    URL = 'https://valorant-api.com/v1/agents'
    response = requests.get(URL, timeout=10)
    response.raise_for_status()
    data = response.json()
    get_data = data['data']

    agent_list = []

    for i in get_data:
        if not i.get('isPlayableCharacter'):
            continue

        role = i.get('role') or {}

        details = {
            'name': i['displayName'],
            'role': role.get('displayName', ''),
            'displayIcon': i.get('displayIcon') or '',
            'uuid': i.get('uuid') or '',
        }

        if not details['uuid'] or not details['name']:
            continue

        agent_list.append(details)

    return agent_list


def sync_agents_to_db():
    """Fetch playable agents and upsert into local DB."""
    remote_agents = get_agent_data()

    # Deduplicate by visible name first to avoid duplicate display entries.
    unique_by_name = {}
    for agent in remote_agents:
        if agent['name'] not in unique_by_name:
            unique_by_name[agent['name']] = agent

    for agent in unique_by_name.values():
        Agent.objects.update_or_create(
            valorant_uuid=agent['uuid'],
            defaults={
                'name': agent['name'],
                'role': agent['role'],
                'display_icon': agent['displayIcon'],
                'is_active': True,
            },
        )


def sync_agents_if_stale(max_age_hours=SYNC_MAX_AGE_HOURS):
    # Prevent overlapping sync writes from concurrent requests.
    with SYNC_LOCK:
        latest_update = Agent.objects.filter(is_active=True).order_by('-updated_at').values_list('updated_at', flat=True).first()
        if latest_update is None:
            sync_agents_to_db()
            return

        age_limit = timezone.now() - timedelta(hours=max_age_hours)
        if latest_update < age_limit:
            sync_agents_to_db()


def get_random_assignments(players):
    """Return unique agent assignments for player payload.

    players: list[dict] with keys id, name, preferredRole
    """
    sync_agents_if_stale()

    available_agents = list(Agent.objects.filter(is_active=True).values('name', 'role', 'display_icon'))

    if len(available_agents) < len(players):
        return None

    return _build_unique_assignments(players, available_agents)
    