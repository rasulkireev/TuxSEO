import json
from unittest.mock import Mock, patch

import pytest
import requests
from django import forms
from django.contrib.auth.models import User
from django.test import RequestFactory, override_settings

from core.forms import AutoSubmissionSettingForm, CustomSignUpForm, ProfileUpdateForm


class TestAutoSubmissionSettingForm:
    def test_clean_body_returns_dict_as_is(self):
        form = AutoSubmissionSettingForm()
        form.cleaned_data = {"body": {"title": "hello"}}

        cleaned_body = form.clean_body()

        assert cleaned_body == {"title": "hello"}

    def test_clean_body_parses_json_string_to_dict(self):
        form = AutoSubmissionSettingForm()
        form.cleaned_data = {"body": '{"title": "hello"}'}

        cleaned_body = form.clean_body()

        assert cleaned_body == {"title": "hello"}

    def test_clean_body_returns_empty_dict_for_empty_string(self):
        form = AutoSubmissionSettingForm()
        form.cleaned_data = {"body": ""}

        cleaned_body = form.clean_body()

        assert cleaned_body == {}

    def test_clean_body_raises_error_for_invalid_json(self):
        form = AutoSubmissionSettingForm()
        form.cleaned_data = {"body": "{invalid-json}"}

        with pytest.raises(json.JSONDecodeError):
            form.clean_body()


class TestCustomSignUpFormTurnstile:
    @override_settings(CLOUDFLARE_TURNSTILE_SECRET_KEY="secret-key")
    @patch("core.forms.requests.post")
    def test_verify_turnstile_token_returns_true_on_success(self, mock_post):
        mock_response = Mock()
        mock_response.json.return_value = {"success": True}
        mock_post.return_value = mock_response

        form = CustomSignUpForm()

        is_valid = form._verify_turnstile_token("test-token")

        assert is_valid is True

    @override_settings(CLOUDFLARE_TURNSTILE_SECRET_KEY="secret-key")
    @patch("core.forms.requests.post")
    def test_verify_turnstile_token_returns_false_when_api_reports_failure(self, mock_post):
        mock_response = Mock()
        mock_response.json.return_value = {
            "success": False,
            "error-codes": ["invalid-input-response"],
        }
        mock_post.return_value = mock_response

        form = CustomSignUpForm()

        is_valid = form._verify_turnstile_token("test-token")

        assert is_valid is False

    @override_settings(CLOUDFLARE_TURNSTILE_SECRET_KEY="secret-key")
    @patch("core.forms.requests.post", side_effect=requests.RequestException("network error"))
    def test_verify_turnstile_token_returns_false_on_request_exception(self, mock_post):
        form = CustomSignUpForm()

        is_valid = form._verify_turnstile_token("test-token")

        assert is_valid is False

    @override_settings(
        CLOUDFLARE_TURNSTILE_SITEKEY="site-key",
        CLOUDFLARE_TURNSTILE_SECRET_KEY="",
    )
    @patch("allauth.account.forms.SignupForm.clean", return_value={})
    def test_clean_requires_turnstile_token_when_site_key_is_configured(self, mock_signup_clean):
        form = CustomSignUpForm(data={})
        form.request = RequestFactory().post("/accounts/signup/")

        with pytest.raises(forms.ValidationError, match="Please complete the verification challenge"):
            form.clean()

    @override_settings(
        CLOUDFLARE_TURNSTILE_SITEKEY="site-key",
        CLOUDFLARE_TURNSTILE_SECRET_KEY="secret-key",
    )
    @patch("allauth.account.forms.SignupForm.clean", return_value={})
    @patch.object(CustomSignUpForm, "_verify_turnstile_token", return_value=True)
    def test_clean_passes_remote_ip_to_turnstile_verification(
        self, mock_verify_turnstile_token, mock_signup_clean
    ):
        remote_ip = "203.0.113.10"
        form = CustomSignUpForm(data={"cf-turnstile-response": "test-token"})
        form.request = RequestFactory().post("/accounts/signup/", REMOTE_ADDR=remote_ip)

        cleaned_data = form.clean()

        assert cleaned_data == {}
        mock_verify_turnstile_token.assert_called_once_with("test-token", remote_ip)


@pytest.mark.django_db
class TestProfileUpdateForm:
    def test_save_updates_user_fields_from_form_data(self):
        user = User.objects.create_user(
            username="profile-user",
            email="before@example.com",
            password="secret",
            first_name="Before",
            last_name="Name",
        )

        profile = user.profile

        form = ProfileUpdateForm(
            data={
                "first_name": "After",
                "last_name": "Updated",
                "email": "after@example.com",
            },
            instance=profile,
        )

        assert form.is_valid()

        updated_profile = form.save()

        user.refresh_from_db()
        assert updated_profile.id == profile.id
        assert user.first_name == "After"
        assert user.last_name == "Updated"
        assert user.email == "after@example.com"
