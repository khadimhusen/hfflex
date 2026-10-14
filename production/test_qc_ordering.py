from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from production.models import JobQc, ProdReport
from quality.models import QCTest


class QcListOrderingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('qcadmin', 'q@example.com', 'x')
        cls.anil = User.objects.create_user('qanil', first_name='Anil', last_name='Zed')
        cls.zoya = User.objects.create_user('qzoya', first_name='Zoya', last_name='Abe')
        cls.report = ProdReport.objects.order_by('id').first()
        cls.test = QCTest.objects.order_by('id').first()

    def make(self, user, result):
        return JobQc.objects.create(prodreport=self.report, qctest=self.test, result=result, createdby=user)

    def ids(self, ordering):
        """The ids of the one report's QC rows, in the API's order (a report has few)."""
        client = APIClient()
        client.force_authenticate(self.admin)
        ids, page = [], 1
        while True:
            data = client.get('/api/production/jobqcs/', {'ordering': ordering, 'prodreport': self.report.pk, 'page_size': 100, 'page': page}).json()
            ids += [r['id'] for r in data['results']]
            if not data.get('next'):
                return ids
            page += 1

    def setUp(self):
        if self.report is None or self.test is None:
            self.skipTest('needs an existing production report and QC test')
        self.a = self.make(self.zoya, 'b')
        self.b = self.make(self.anil, 'c')
        self.c = self.make(self.zoya, 'a')

    def mine(self, ordering):
        wanted = {self.a.pk, self.b.pk, self.c.pk}
        return [i for i in self.ids(ordering) if i in wanted]

    def test_sort_by_created_by_ascending_and_descending(self):
        asc = self.mine('created_by_name')
        self.assertEqual(asc, [self.b.pk, self.a.pk, self.c.pk])      # Anil, then Zoya (ties by id)
        self.assertEqual(self.mine('-created_by_name'), [self.a.pk, self.c.pk, self.b.pk])  # Zoya, then Anil

    def test_sort_by_result(self):
        self.assertEqual(self.mine('result'), [self.c.pk, self.a.pk, self.b.pk])
        self.assertEqual(self.mine('-result'), [self.b.pk, self.a.pk, self.c.pk])

    def test_sort_by_created(self):
        self.assertEqual(self.mine('created'), [self.a.pk, self.b.pk, self.c.pk])
        self.assertEqual(self.mine('-created'), [self.c.pk, self.b.pk, self.a.pk])

    def test_default_order_is_unchanged(self):
        self.assertEqual(self.mine(''), [self.a.pk, self.b.pk, self.c.pk])
