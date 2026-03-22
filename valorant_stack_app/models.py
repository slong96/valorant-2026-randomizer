from django.db import models

class Agent(models.Model):
	valorant_uuid = models.CharField(max_length=64, unique=True)
	name = models.CharField(max_length=100, unique=True)
	role = models.CharField(max_length=100, blank=True)
	display_icon = models.URLField(max_length=500, blank=True)
	is_active = models.BooleanField(default=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return self.name
