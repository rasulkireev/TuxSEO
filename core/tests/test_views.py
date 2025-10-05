import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.mark.django_db
class TestHomeView:
    def test_home_view_status_code(self, client):
        url = reverse("home")
        response = client.get(url)
        assert response.status_code == 200

    def test_home_view_uses_correct_template(self, client):
        url = reverse("home")
        response = client.get(url)
        assert "pages/home.html" in [t.name for t in response.templates]
