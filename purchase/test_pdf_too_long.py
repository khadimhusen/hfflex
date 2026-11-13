import os
from types import SimpleNamespace
from unittest import mock

from django.conf import settings
from django.test import RequestFactory, SimpleTestCase
from rest_framework.test import APIRequestFactory

from purchase import api_viewsets, pdfviews
from purchase.pdfviews import PoPdfTooLong


class PoPdfTooLongTests(SimpleTestCase):
    """An order whose item table cannot fit a page must show staff a clear
    message instead of a bare "Server Error (500)" -- while the builder still
    refuses to print an order with items silently missing. (No database
    needed: the builder is made to raise exactly what it raises for a PO
    whose table does not fit.)"""

    def test_error_is_still_a_runtime_error_and_explains_the_fix(self):
        error = PoPdfTooLong(3910)
        self.assertIsInstance(error, RuntimeError)
        self.assertIn('#3910', error.user_message)
        self.assertIn('too long', error.user_message)
        self.assertIn('would have been silently dropped', str(error))

    def test_old_page_shows_the_message_with_status_422(self):
        request = RequestFactory().get('/purchase/purchasepdf/3910')
        request.user = mock.Mock(is_authenticated=True)
        with mock.patch.object(pdfviews, 'get_object_or_404'), \
                mock.patch.object(pdfviews, 'build_po_pdf_buffer', side_effect=PoPdfTooLong(3910)), \
                self.assertLogs('django', level='ERROR') as logs:
            response = pdfviews.newpopdf(request, 3910)
        self.assertEqual(response.status_code, 422)
        body = response.content.decode()
        self.assertIn('Purchase Order #3910 cannot be printed', body)
        self.assertIn('Go back', body)
        self.assertTrue(any('3910' in line for line in logs.output))

    def test_old_page_still_returns_the_pdf_when_it_fits(self):
        import io
        request = RequestFactory().get('/purchase/purchasepdf/1')
        request.user = mock.Mock(is_authenticated=True)
        po = mock.Mock(id=1, supplier='S')
        with mock.patch.object(pdfviews, 'get_object_or_404', return_value=po), \
                mock.patch.object(pdfviews, 'build_po_pdf_buffer', return_value=io.BytesIO(b'%PDF-1.4 fake')):
            response = pdfviews.newpopdf(request, 1)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Disposition'], 'attachment; filename="1 - S.pdf"')

    def test_api_returns_the_message_as_detail_with_status_422(self):
        viewset = api_viewsets.PoViewSet()
        viewset.request = APIRequestFactory().get('/')
        viewset.get_object = lambda: mock.Mock(id=3910)
        with mock.patch.object(api_viewsets, 'build_po_pdf_buffer', side_effect=PoPdfTooLong(3910)), \
                self.assertLogs('django', level='ERROR'):
            response = viewset.pdf(viewset.request, pk=3910)
        self.assertEqual(response.status_code, 422)
        self.assertIn('Purchase Order #3910', response.data['detail'])


class PoPdfLogoTests(SimpleTestCase):
    """Which logo (if any) the PO PDF draws in its top-left corner."""

    HF_LOGO = os.path.join(settings.BASE_DIR, 'static', 'images', 'hflogo.png')

    def test_no_logo_for_a_company_that_has_none(self):
        lh = SimpleNamespace(company=SimpleNamespace(logo=None), logo_url='')
        self.assertIsNone(pdfviews.letterhead_logo_path(lh))

    def test_a_missing_file_is_ignored_not_an_error(self):
        company = SimpleNamespace(logo=SimpleNamespace(path='/no/such/logo.png'))
        self.assertIsNone(pdfviews.letterhead_logo_path(SimpleNamespace(company=company, logo_url='/x')))

    def test_companys_own_logo_wins_over_the_classic_one(self):
        company = SimpleNamespace(logo=SimpleNamespace(path=__file__))  # any file that exists
        lh = SimpleNamespace(company=company, logo_url='/media/company/x.png')
        self.assertEqual(pdfviews.letterhead_logo_path(lh), __file__)

    def test_hf_flex_without_its_own_logo_uses_the_classic_logo(self):
        if not os.path.isfile(self.HF_LOGO):  # static/ is not in git
            self.skipTest('static/images/hflogo.png is not on this machine')
        lh = SimpleNamespace(company=SimpleNamespace(logo=None), logo_url=pdfviews.LEGACY_LOGO_URL)
        self.assertEqual(pdfviews.letterhead_logo_path(lh), self.HF_LOGO)


class NumberedCanvasTests(SimpleTestCase):
    """The PO PDF prints "Page x of y" on every page, including the last one
    (which save() closes rather than showPage())."""

    def make(self, pages):
        import io
        from reportlab.lib.pagesizes import A4
        calls = []

        class Recording(pdfviews.NumberedCanvas):
            def draw_page_number(self, number, total):
                calls.append((number, total))

        c = Recording(io.BytesIO(), pagesize=A4)
        for n in range(pages):
            c.drawString(50, 700, f'content {n}')
            if n < pages - 1:
                c.showPage()
        c.save()
        return calls, c

    def test_every_page_is_numbered_out_of_the_total(self):
        calls, _ = self.make(3)
        self.assertEqual(calls, [(1, 3), (2, 3), (3, 3)])

    def test_a_single_page_is_page_1_of_1(self):
        calls, _ = self.make(1)
        self.assertEqual(calls, [(1, 1)])

    def test_the_text_is_drawn_for_real(self):
        import io
        from reportlab.lib.pagesizes import A4
        buffer = io.BytesIO()
        c = pdfviews.NumberedCanvas(buffer, pagesize=A4)
        c.drawString(50, 700, 'x')
        c.showPage()
        c.drawString(50, 700, 'y')
        c.save()
        self.assertEqual(buffer.getvalue().count(b'/Type /Page\n'), 2)
