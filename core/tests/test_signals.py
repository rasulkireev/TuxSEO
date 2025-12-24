from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.db import connection

from core.models import Profile, ProfileStates


@pytest.mark.django_db
class TestCreateUserProfile:
    def test_creates_profile_when_user_is_created(self):
        """Test that a Profile is automatically created when a User is created."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        assert Profile.objects.filter(user=user).exists()
        profile = Profile.objects.get(user=user)
        assert profile.user == user

    @patch("core.models.async_task")
    def test_tracks_state_change_to_signed_up_on_user_creation(self, mock_async_task):
        """Test that track_state_change is called with SIGNED_UP state when user is created."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        profile = Profile.objects.get(user=user)

        assert mock_async_task.called
        call_args = mock_async_task.call_args
        assert call_args[0][0] == "core.tasks.track_state_change"
        assert call_args[1]["profile_id"] == profile.id
        assert call_args[1]["to_state"] == ProfileStates.SIGNED_UP
        assert call_args[1]["group"] == "Track State Change"

    def test_does_not_create_profile_when_user_is_updated(self):
        """Test that a Profile is not created when an existing User is updated."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        initial_profile_count = Profile.objects.count()

        user.first_name = "Updated"
        user.save()

        assert Profile.objects.count() == initial_profile_count

    def test_makes_user_staff_and_superuser_when_id_is_one(self):
        """Test that user with id=1 is automatically made staff and superuser."""
        User.objects.all().delete()

        # Reset the PostgreSQL sequence to ensure the next user gets id=1
        with connection.cursor() as cursor:
            cursor.execute("SELECT setval(pg_get_serial_sequence('auth_user', 'id'), 1, false)")

        user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
        )

        user.refresh_from_db()
        assert user.id == 1
        assert user.is_staff is True
        assert user.is_superuser is True

    def test_does_not_make_user_staff_when_id_is_not_one(self):
        """Test that users with id != 1 are not automatically made staff."""
        user = User.objects.create_user(
            username="regularuser",
            email="regular@example.com",
            password="regularpass123",
        )

        user.refresh_from_db()
        assert user.id != 1
        assert user.is_staff is False
        assert user.is_superuser is False
