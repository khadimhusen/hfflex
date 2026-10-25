"""Public information pages (no login): home/about, privacy policy, terms.

These exist so the app has real, reachable URLs for things that need them,
e.g. the Google OAuth consent screen (app home page / privacy policy / terms).
Nothing on these pages needs a session or the database.
"""
from django.views.generic import TemplateView

BUSINESS_NAME = "HF Flex"
CONTACT_EMAIL = "khadimhusen@gmail.com"
POLICY_UPDATED = "25 October 2026"


class PublicPage(TemplateView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            business_name=BUSINESS_NAME,
            contact_email=CONTACT_EMAIL,
            policy_updated=POLICY_UPDATED,
        )
        return context


class AboutView(PublicPage):
    template_name = "public/about.html"


class PrivacyView(PublicPage):
    template_name = "public/privacy.html"


class TermsView(PublicPage):
    template_name = "public/terms.html"
