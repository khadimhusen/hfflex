from unittest import mock

from django.test import SimpleTestCase

from .defaults import HF_FLEX
from .letterhead import LEGACY_LOGO_URL, letterhead
from .models import Company


def company(**extra):
    """An unsaved Company -- letterhead() only reads attributes."""
    values = dict(name='H F PRINTPACK PVT. LTD.', short_name='HP', gstin='27AAHCH0731K1ZL',
                  address_line1='Gat no. 101/1/1, Gardi, Vita', address_line2='Tal- Khanapur',
                  phone='8552827683', email='hfprintpack@gmail.com', website='')
    values.update(extra)
    return Company(**values)


class LetterheadTests(SimpleTestCase):
    def test_uses_the_companys_own_details(self):
        lh = letterhead(company())
        self.assertEqual(lh.name, 'H F PRINTPACK PVT. LTD.')
        self.assertEqual(lh.gstin, '27AAHCH0731K1ZL')
        self.assertEqual(lh.address_line1, 'Gat no. 101/1/1, Gardi, Vita')
        self.assertEqual(lh.address_line2, 'Tal- Khanapur')
        self.assertEqual(lh.phone, '8552827683')
        self.assertEqual(lh.email, 'hfprintpack@gmail.com')
        self.assertEqual(lh.website, '')

    def test_title_is_the_mixed_case_name_the_pdf_header_uses(self):
        self.assertEqual(letterhead(company(name='H F FLEX PVT. LTD.')).title_name, 'H F Flex Pvt. Ltd.')
        self.assertEqual(letterhead(company()).title_name, 'H F Printpack Pvt. Ltd.')

    def test_watermark_drops_the_legal_suffix(self):
        for name, expected in [
            ('H F FLEX PVT. LTD.', 'H F FLEX'),
            ('H F PRINTPACK PVT. LTD.', 'H F PRINTPACK'),
            ('H F PRINTPACK PRIVATE LIMITED', 'H F PRINTPACK'),
            ('h f flex pvt ltd', 'H F FLEX'),
            ('ACME', 'ACME'),  # no suffix to drop
        ]:
            self.assertEqual(letterhead(company(name=name)).watermark, expected, name)

    def test_no_company_means_the_default_company(self):
        default = company(name='THE DEFAULT PVT. LTD.')
        with mock.patch('company.letterhead.default_company', return_value=default):
            self.assertEqual(letterhead(None).name, 'THE DEFAULT PVT. LTD.')
            self.assertEqual(letterhead().name, 'THE DEFAULT PVT. LTD.')

    def test_with_no_company_rows_at_all_it_falls_back_to_h_f_flex(self):
        with mock.patch('company.letterhead.default_company', return_value=None):
            lh = letterhead(None)
        self.assertEqual(lh.name, HF_FLEX['name'])
        self.assertEqual(lh.gstin, HF_FLEX['gstin'])
        self.assertEqual(lh.address_line1, HF_FLEX['address_line1'])
        self.assertEqual(lh.title_name, 'H F Flex Pvt. Ltd.')
        self.assertEqual(lh.watermark, 'H F FLEX')
        self.assertIsNone(lh.company)

    def test_legacy_logo_only_for_a_company_with_h_f_flexs_gstin(self):
        self.assertEqual(letterhead(company(gstin=HF_FLEX['gstin'])).logo_url, LEGACY_LOGO_URL)
        self.assertEqual(letterhead(company()).logo_url, '')  # another company never gets H F Flex's logo
        self.assertEqual(letterhead(company(gstin='')).logo_url, '')
