import re
from types import SimpleNamespace

from .defaults import HF_FLEX
from .models import default_company

# " PVT. LTD." / " PRIVATE LIMITED" at the end of a company name.
_LEGAL_SUFFIX = re.compile(r'\s*\b(PVT\.?|PRIVATE)\s*(LTD\.?|LIMITED)\s*$', re.IGNORECASE)

# The logo the old on-screen purchase order page showed for H F Flex before
# companies had logos of their own. Used only for a company that has none and
# carries H F Flex's GSTIN; remove once logos are uploaded in the admin.
LEGACY_LOGO_URL = '/static/images/hflogo.png'


def letterhead(company=None):
    """What a document prints at the top for one of our companies.

    `company` is a Company, or None for "the default company". If there is no
    Company row at all it falls back to the H F Flex details that used to be
    typed into the documents, so printing never fails for want of one.
    """
    company = company or default_company()
    source = company if company is not None else SimpleNamespace(
        pk=None, logo=None, **{k: v for k, v in HF_FLEX.items() if k != 'is_default'})

    logo_url = ''
    if getattr(source, 'logo', None):
        logo_url = source.logo.url
    elif source.gstin == HF_FLEX['gstin']:
        logo_url = LEGACY_LOGO_URL

    name = source.name.strip()
    return SimpleNamespace(
        company=company,
        name=name,
        # "H F Flex Pvt. Ltd." -- the mixed-case form the PDF header uses.
        title_name=name.title(),
        # "H F FLEX" -- the repeated watermark down the PDF's side strip.
        watermark=_LEGAL_SUFFIX.sub('', name).strip().upper(),
        gstin=source.gstin,
        address_line1=source.address_line1,
        address_line2=source.address_line2,
        phone=source.phone,
        email=source.email,
        website=source.website,
        logo_url=logo_url,
    )
