import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from crm.models import Deal, DealStage, Lead, Pipeline

# Dates in 2001, so only the rows made here can match (real data starts in 2023).
DAY = datetime.datetime(2001, 3, 1)


def stamp(model, pk, moment):
    model.objects.filter(pk=pk).update(created_at=moment)


class CreatedAndSourceBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('crmfilt', 'f@example.com', 'x')
        pipeline = Pipeline.objects.first()
        stage = DealStage.objects.filter(pipeline=pipeline).first()
        #            created_at                       source
        spec = [(DAY, 'Indiamart'),                                         # 1 March, midnight
                (DAY + datetime.timedelta(hours=23, minutes=59, seconds=59), 'INDIAMART'),   # 1 March, last second
                (DAY + datetime.timedelta(days=1), 'Cold Call')]            # 2 March, midnight
        cls.leads, cls.deals = [], []
        for i, (moment, source) in enumerate(spec):
            lead = Lead.objects.create(last_name=f'TESTFILT{i}', owner=cls.user, lead_source=source)
            deal = Deal.objects.create(name=f'TESTFILT{i}', pipeline=pipeline, stage=stage, owner=cls.user,
                                       lead_source=source, closing_date=moment.date())
            stamp(Lead, lead.pk, moment)
            stamp(Deal, deal.pk, moment)
            cls.leads.append(lead)
            cls.deals.append(deal)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def ids(self, path, **params):
        response = self.client.get(path, {**params, 'page_size': 100})
        self.assertEqual(response.status_code, 200, response.content)
        return {row['id'] for row in response.json()['results']}


class LeadFilterTests(CreatedAndSourceBase):
    path = '/api/crm/leads/'

    def pks(self, *indexes):
        return {self.leads[i].pk for i in indexes}

    def test_created_from_keeps_that_day_and_later(self):
        # (an upper bound keeps the real 2023+ leads out of the answer)
        self.assertEqual(self.ids(self.path, created_from='2001-03-02', created_to='2001-12-31'), self.pks(2))
        self.assertEqual(self.ids(self.path, created_from='2001-03-01', created_to='2001-03-31'), self.pks(0, 1, 2))

    def test_created_to_includes_the_whole_last_day(self):
        self.assertEqual(self.ids(self.path, created_from='2001-01-01', created_to='2001-03-01'), self.pks(0, 1))

    def test_one_day_range(self):
        self.assertEqual(self.ids(self.path, created_from='2001-03-01', created_to='2001-03-01'), self.pks(0, 1))

    def test_from_after_to_is_empty(self):
        self.assertEqual(self.ids(self.path, created_from='2001-03-05', created_to='2001-03-01'), set())

    def test_a_bad_date_is_a_400(self):
        self.assertEqual(self.client.get(self.path, {'created_from': 'yesterday'}).status_code, 400)

    def test_source_ignores_case_but_matches_the_whole_value(self):
        window = dict(created_from='2001-01-01', created_to='2001-12-31')
        self.assertEqual(self.ids(self.path, lead_source='indiamart', **window), self.pks(0, 1))
        self.assertEqual(self.ids(self.path, lead_source='INDIAMART', **window), self.pks(0, 1))
        self.assertEqual(self.ids(self.path, lead_source='Cold Call', **window), self.pks(2))
        self.assertEqual(self.ids(self.path, lead_source='India', **window), set())

    def test_it_combines_with_the_other_filters(self):
        self.assertEqual(self.ids(self.path, created_from='2001-03-01', created_to='2001-03-01',
                                  lead_source='cold call'), set())
        self.assertEqual(self.ids(self.path, created_from='2001-03-02', created_to='2001-03-02',
                                  lead_source='cold call'), self.pks(2))


class DealFilterTests(CreatedAndSourceBase):
    path = '/api/crm/deals/'

    def pks(self, *indexes):
        return {self.deals[i].pk for i in indexes}

    def test_created_range_includes_both_days(self):
        self.assertEqual(self.ids(self.path, created_from='2001-03-01', created_to='2001-03-01'), self.pks(0, 1))
        self.assertEqual(self.ids(self.path, created_from='2001-03-02', created_to='2001-03-02'), self.pks(2))
        self.assertEqual(self.ids(self.path, created_from='2001-01-01', created_to='2001-12-31'), self.pks(0, 1, 2))

    def test_source_filter_ignores_case_and_matches_all_spellings(self):
        window = dict(created_from='2001-01-01', created_to='2001-12-31')
        self.assertEqual(self.ids(self.path, lead_source='Indiamart', **window), self.pks(0, 1))
        self.assertEqual(self.ids(self.path, lead_source='cold call', **window), self.pks(2))
        self.assertEqual(self.ids(self.path, lead_source='Google+', **window), set())

    def test_the_totals_row_uses_the_same_filters(self):
        response = self.client.get('/api/crm/deals/summary/',
                                   {'created_from': '2001-03-01', 'created_to': '2001-03-01', 'lead_source': 'indiamart'})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['count'], 2)

    def test_the_old_closing_date_filter_still_works(self):
        got = self.ids(self.path, closing_date__gte='2001-03-02', closing_date__lte='2001-03-02')
        self.assertEqual(got, self.pks(2))

    def test_a_bad_date_is_a_400(self):
        self.assertEqual(self.client.get(self.path, {'created_to': '32/13/2001'}).status_code, 400)
