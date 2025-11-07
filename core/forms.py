import requests
from allauth.account.forms import LoginForm, SignupForm
from django import forms
from django.conf import settings

from core.models import AutoSubmissionSetting, Profile, Project
from core.utils import DivErrorList
from tuxseo.utils import get_tuxseo_logger

logger = get_tuxseo_logger(__name__)

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


class CustomSignUpForm(SignupForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.error_class = DivErrorList

    def clean(self):
        cleaned_data = super().clean()

        if settings.CLOUDFLARE_TURNSTILE_SECRET_KEY:
            turnstile_token = self.data.get("cf-turnstile-response", "")

            if not turnstile_token:
                logger.warning("[Turnstile Validation] Missing Turnstile token in signup form")
                raise forms.ValidationError("Please complete the verification challenge.")

            user_ip = self.request.META.get("REMOTE_ADDR", "")
            is_valid = self._verify_turnstile_token(turnstile_token, user_ip)

            if not is_valid:
                logger.warning("[Turnstile Validation] Invalid Turnstile token in signup form")
                raise forms.ValidationError("Verification failed. Please try again.")

        return cleaned_data

    def _verify_turnstile_token(self, token):
        try:
            response = requests.post(
                TURNSTILE_VERIFY_URL,
                data={
                    "secret": settings.CLOUDFLARE_TURNSTILE_SECRET_KEY,
                    "response": token,
                },
                timeout=10,
            )

            result = response.json()
            success = result.get("success", False)

            if not success:
                logger.warning(
                    "[Turnstile Validation] Verification failed",
                    error_codes=result.get("error-codes", []),
                )

            return success

        except requests.RequestException as error:
            logger.error(
                "[Turnstile Validation] Request error during verification",
                error=str(error),
                exc_info=True,
            )
            return False


class CustomLoginForm(LoginForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.error_class = DivErrorList


class ProfileUpdateForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=30)
    email = forms.EmailField()

    class Meta:
        model = Profile
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name
            self.fields["email"].initial = self.instance.user.email

    def save(self, commit=True):
        profile = super().save(commit=False)
        user = profile.user
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            profile.save()
        return profile


class ProjectScanForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["url"]


class AutoSubmissionSettingForm(forms.ModelForm):
    TIMEZONE_CHOICES = [
        ("UTC", "UTC"),
        ("America/New_York", "America/New_York"),
        ("America/Chicago", "America/Chicago"),
        ("America/Denver", "America/Denver"),
        ("America/Los_Angeles", "America/Los_Angeles"),
        ("Europe/London", "Europe/London"),
        ("Europe/Paris", "Europe/Paris"),
        ("Asia/Tokyo", "Asia/Tokyo"),
        ("Asia/Shanghai", "Asia/Shanghai"),
        ("Asia/Kolkata", "Asia/Kolkata"),
        ("Australia/Sydney", "Australia/Sydney"),
    ]
    preferred_timezone = forms.ChoiceField(choices=TIMEZONE_CHOICES, required=False)

    class Meta:
        model = AutoSubmissionSetting
        fields = [
            "endpoint_url",
            "body",
            "header",
            "posts_per_month",
            # "preferred_timezone",
            # "preferred_time",
        ]

    def clean_body(self):
        import json

        data = self.cleaned_data["body"]
        if isinstance(data, dict):
            return data
        try:
            return json.loads(data) if data else {}
        except Exception:
            raise
