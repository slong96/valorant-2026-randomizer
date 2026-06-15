import json
import random

from django.http import JsonResponse
from django.shortcuts import render

from .api import get_random_assignments, sync_agents_if_stale
from .models import Agent


ALLOWED_ROLES = {'Duelist', 'Initiator', 'Controller', 'Sentinel'}

def home(request):
    return render(request, 'home.html')


def about(request):
    return render(request, 'about.html')


def custom_404(request, exception=None):
    return render(request, '404.html', status=404)


def get_agents(request):
    sync_agents_if_stale()

    data = list(Agent.objects.filter(is_active=True).values('name', 'role', 'display_icon'))
    normalized = [
        {
            'name': agent['name'],
            'role': agent['role'],
            'displayIcon': agent['display_icon'],
        }
        for agent in data
    ]

    return JsonResponse(normalized, safe=False)


def randomize_agents(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        payload = json.loads(request.body or '{}')
        players = payload.get('players', [])
        role_counts = payload.get('roleCounts', {})
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON payload'}, status=400)

    if not isinstance(players, list) or not players:
        return JsonResponse({'error': 'Players are required'}, status=400)

    if role_counts is None:
        role_counts = {}

    if not isinstance(role_counts, dict):
        return JsonResponse({'error': 'Invalid role counts payload'}, status=400)

    normalized_role_counts = {}
    for role_name, count in role_counts.items():
        normalized_role = str(role_name).strip().title()
        if normalized_role not in ALLOWED_ROLES:
            return JsonResponse({'error': 'Invalid role selection'}, status=400)

        try:
            normalized_count = int(count)
        except (TypeError, ValueError):
            return JsonResponse({'error': 'Invalid role count value'}, status=400)

        if normalized_count < 0:
            return JsonResponse({'error': 'Role count cannot be negative'}, status=400)

        normalized_role_counts[normalized_role] = normalized_count

    cleaned_players = []
    for player in players:
        if not isinstance(player, dict):
            continue

        player_id = player.get('id')
        player_name = str(player.get('name', '')).strip()
        if player_id is None or not player_name:
            continue

        cleaned_players.append({'id': player_id, 'name': player_name, 'preferredRole': ''})

    if not cleaned_players:
        return JsonResponse({'error': 'No valid players provided'}, status=400)

    selected_role_total = sum(normalized_role_counts.values())
    if selected_role_total > len(cleaned_players):
        return JsonResponse({'error': 'Selected role counts cannot exceed number of players'}, status=400)

    if selected_role_total:
        randomized_role_pool = []
        for role_name, count in normalized_role_counts.items():
            randomized_role_pool.extend([role_name] * count)

        random.shuffle(randomized_role_pool)

        priority_players = random.sample(cleaned_players, len(randomized_role_pool))
        for player, selected_role in zip(priority_players, randomized_role_pool):
            player['preferredRole'] = selected_role

    try:
        assignments = get_random_assignments(cleaned_players)
    except Exception:
        return JsonResponse({'error': 'Failed to load agent data'}, status=503)

    if assignments is None:
        return JsonResponse({'error': 'Could not satisfy role selections with unique agents'}, status=400)

    assignments_by_player = {assignment['id']: assignment for assignment in assignments}
    for player in cleaned_players:
        assignments_by_player[player['id']]['requiredRole'] = player['preferredRole']

    return JsonResponse({'assignments': assignments})