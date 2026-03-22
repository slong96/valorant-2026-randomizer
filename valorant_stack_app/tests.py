import json
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Agent


class ValorantStackAppTests(TestCase):
	def setUp(self):
		self.agent_one = Agent.objects.create(
			valorant_uuid='agent-1',
			name='Jett',
			role='Duelist',
			display_icon='https://example.com/jett.png',
			is_active=True,
		)
		self.agent_two = Agent.objects.create(
			valorant_uuid='agent-2',
			name='Sage',
			role='Sentinel',
			display_icon='https://example.com/sage.png',
			is_active=True,
		)
		self.agent_three = Agent.objects.create(
			valorant_uuid='agent-3',
			name='Sova',
			role='Initiator',
			display_icon='https://example.com/sova.png',
			is_active=True,
		)

	def test_home_page_loads(self):
		response = self.client.get(reverse('home'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Valorant Agent Randomizer')

	def test_about_page_loads(self):
		response = self.client.get(reverse('about'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'About | Valorant Agent Randomizer')
		self.assertContains(response, 'This randomizer helps your squad quickly assign unique VALORANT agents')

	def test_home_page_nav_contains_about_and_github_links(self):
		response = self.client.get(reverse('home'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, f'href="{reverse("home")}"')
		self.assertContains(response, f'href="{reverse("about")}"')
		self.assertContains(response, 'href="https://github.com/"')

	def test_custom_404_page_nav_contains_about_and_github_links(self):
		response = self.client.get('/this-page-does-not-exist/')

		self.assertEqual(response.status_code, 404)
		self.assertContains(response, f'href="{reverse("home")}"', status_code=404)
		self.assertContains(response, f'href="{reverse("about")}"', status_code=404)
		self.assertContains(response, 'href="https://github.com/"', status_code=404)

	def test_unknown_url_uses_custom_404_page(self):
		response = self.client.get('/this-page-does-not-exist/')

		self.assertEqual(response.status_code, 404)
		self.assertContains(response, 'Page Not Found', status_code=404)
		self.assertContains(response, 'Return Home', status_code=404)

	def test_get_agents_returns_database_agents(self):
		response = self.client.get(reverse('get_agents'))

		self.assertEqual(response.status_code, 200)
		data = response.json()

		self.assertEqual(len(data), 3)
		self.assertEqual(
			data[0],
			{
				'name': 'Jett',
				'role': 'Duelist',
				'displayIcon': 'https://example.com/jett.png',
			},
		)

	def test_randomize_agents_returns_unique_agents_for_duplicate_player_names(self):
		payload = {
			'players': [
				{'id': 1, 'name': 'Chris'},
				{'id': 2, 'name': 'Chris'},
			]
		}

		response = self.client.post(
			reverse('randomize_agents'),
			data=json.dumps(payload),
			content_type='application/json',
		)

		self.assertEqual(response.status_code, 200)
		assignments = response.json()['assignments']

		self.assertEqual(len(assignments), 2)
		self.assertCountEqual([item['id'] for item in assignments], [1, 2])
		self.assertEqual([item['playerName'] for item in assignments], ['Chris', 'Chris'])
		self.assertEqual(len({item['agent']['name'] for item in assignments}), 2)

	def test_randomize_agents_returns_400_when_not_enough_agents_exist(self):
		Agent.objects.exclude(pk=self.agent_one.pk).delete()

		payload = {
			'players': [
				{'id': 1, 'name': 'Chris'},
				{'id': 2, 'name': 'Alex'},
			]
		}

		response = self.client.post(
			reverse('randomize_agents'),
			data=json.dumps(payload),
			content_type='application/json',
		)

		self.assertEqual(response.status_code, 400)
		self.assertEqual(response.json()['error'], 'Could not satisfy role selections with unique agents')

	def test_randomize_agents_honors_role_counts(self):
		# Add enough agents to satisfy all requested role slots uniquely.
		Agent.objects.create(
			valorant_uuid='agent-4',
			name='Raze',
			role='Duelist',
			display_icon='https://example.com/raze.png',
			is_active=True,
		)
		Agent.objects.create(
			valorant_uuid='agent-5',
			name='Brimstone',
			role='Controller',
			display_icon='https://example.com/brimstone.png',
			is_active=True,
		)

		payload = {
			'players': [
				{'id': 1, 'name': 'P1'},
				{'id': 2, 'name': 'P2'},
				{'id': 3, 'name': 'P3'},
				{'id': 4, 'name': 'P4'},
				{'id': 5, 'name': 'P5'},
			],
			'roleCounts': {
				'Duelist': 2,
				'Initiator': 1,
				'Sentinel': 1,
				'Controller': 1,
			},
		}

		response = self.client.post(
			reverse('randomize_agents'),
			data=json.dumps(payload),
			content_type='application/json',
		)

		self.assertEqual(response.status_code, 200)
		assignments = response.json()['assignments']
		self.assertEqual(len(assignments), 5)

		assigned_roles = [item['agent']['role'] for item in assignments]
		self.assertEqual(assigned_roles.count('Duelist'), 2)
		self.assertEqual(assigned_roles.count('Initiator'), 1)
		self.assertEqual(assigned_roles.count('Sentinel'), 1)
		self.assertEqual(assigned_roles.count('Controller'), 1)
		self.assertEqual(len({item['agent']['name'] for item in assignments}), 5)
		self.assertEqual(sum(1 for item in assignments if item['requiredRole']), 5)

	def test_randomize_agents_allows_partial_role_counts(self):
		payload = {
			'players': [
				{'id': 1, 'name': 'A'},
				{'id': 2, 'name': 'B'},
				{'id': 3, 'name': 'C'},
			],
			'roleCounts': {'Duelist': 1},
		}

		response = self.client.post(
			reverse('randomize_agents'),
			data=json.dumps(payload),
			content_type='application/json',
		)

		self.assertEqual(response.status_code, 200)
		assignments = response.json()['assignments']
		self.assertEqual(len(assignments), 3)
		self.assertEqual(sum(1 for item in assignments if item['requiredRole'] == 'Duelist'), 1)
		self.assertEqual(sum(1 for item in assignments if not item['requiredRole']), 2)
		self.assertEqual(sum(1 for item in assignments if item['agent']['role'] == 'Duelist'), 1)

	def test_randomize_agents_returns_400_when_role_count_total_exceeds_players(self):
		payload = {
			'players': [
				{'id': 1, 'name': 'A'},
				{'id': 2, 'name': 'B'},
				{'id': 3, 'name': 'C'},
			],
			'roleCounts': {'Duelist': 4},
		}

		response = self.client.post(
			reverse('randomize_agents'),
			data=json.dumps(payload),
			content_type='application/json',
		)

		self.assertEqual(response.status_code, 400)
		self.assertEqual(response.json()['error'], 'Selected role counts cannot exceed number of players')

	def test_randomize_agents_returns_400_for_invalid_role_name(self):
		payload = {
			'players': [{'id': 1, 'name': 'A'}],
			'roleCounts': {'Sniper': 1},
		}

		response = self.client.post(
			reverse('randomize_agents'),
			data=json.dumps(payload),
			content_type='application/json',
		)

		self.assertEqual(response.status_code, 400)
		self.assertEqual(response.json()['error'], 'Invalid role selection')

	def test_randomize_agents_returns_400_for_negative_role_count(self):
		payload = {
			'players': [{'id': 1, 'name': 'A'}],
			'roleCounts': {'Duelist': -1},
		}

		response = self.client.post(
			reverse('randomize_agents'),
			data=json.dumps(payload),
			content_type='application/json',
		)

		self.assertEqual(response.status_code, 400)
		self.assertEqual(response.json()['error'], 'Role count cannot be negative')

	def test_randomize_agents_returns_400_for_non_numeric_role_count(self):
		payload = {
			'players': [{'id': 1, 'name': 'A'}],
			'roleCounts': {'Duelist': 'abc'},
		}

		response = self.client.post(
			reverse('randomize_agents'),
			data=json.dumps(payload),
			content_type='application/json',
		)

		self.assertEqual(response.status_code, 400)
		self.assertEqual(response.json()['error'], 'Invalid role count value')

	@patch('valorant_stack_app.views.sync_agents_if_stale')
	def test_get_agents_calls_sync_if_stale(self, mocked_sync_if_stale):
		response = self.client.get(reverse('get_agents'))

		self.assertEqual(response.status_code, 200)
		mocked_sync_if_stale.assert_called_once()

	@patch('valorant_stack_app.api.sync_agents_to_db')
	def test_sync_agents_if_stale_calls_sync_when_no_active_agents(self, mocked_sync):
		from .api import sync_agents_if_stale

		Agent.objects.all().delete()
		sync_agents_if_stale(max_age_hours=24)

		mocked_sync.assert_called_once()

	@patch('valorant_stack_app.api.sync_agents_to_db')
	def test_sync_agents_if_stale_does_not_sync_when_data_is_fresh(self, mocked_sync):
		from .api import sync_agents_if_stale

		sync_agents_if_stale(max_age_hours=24)

		mocked_sync.assert_not_called()

	@patch('valorant_stack_app.api.sync_agents_to_db')
	def test_sync_agents_if_stale_calls_sync_when_data_is_old(self, mocked_sync):
		from .api import sync_agents_if_stale

		stale_time = timezone.now() - timedelta(hours=48)
		Agent.objects.filter(pk=self.agent_one.pk).update(updated_at=stale_time)
		Agent.objects.filter(pk=self.agent_two.pk).update(updated_at=stale_time)
		Agent.objects.filter(pk=self.agent_three.pk).update(updated_at=stale_time)

		sync_agents_if_stale(max_age_hours=24)

		mocked_sync.assert_called_once()

	def test_randomize_agents_requires_post(self):
		response = self.client.get(reverse('randomize_agents'))

		self.assertEqual(response.status_code, 405)
		self.assertEqual(response.json()['error'], 'Method not allowed')
