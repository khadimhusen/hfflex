import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from crm.models import Deal, DealStage
from crm.views_dashboard import _add_months


class DashboardClosedLostTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.me = User.objects.create_superuser('dashme', 'd@example.com', 'x')
        cls.other = User.objects.create_user('dashother', 'o@example.com', 'x')
        cls.lost_stage = DealStage.objects.filter(is_lost=True).first()
        cls.won_stage = DealStage.objects.filter(is_won=True).first()
        cls.open_stage = DealStage.objects.filter(is_won=False, is_lost=False).first()

        today = timezone.now().date()
        cls.month_start = today.replace(day=1)
        cls.this_month = cls.month_start + datetime.timedelta(days=2)
        cls.two_months_ago = _add_months(cls.month_start, -2) + datetime.timedelta(days=9)
        cls.too_old = _add_months(cls.month_start, -13) + datetime.timedelta(days=4)

    def deal(self, stage, owner=None, amount='1000', closed=None, name='TESTDASH'):
        return Deal.objects.create(
            name=name, pipeline=stage.pipeline, stage=stage, owner=owner or self.me,
            amount=None if amount is None else Decimal(amount), closing_date=closed or self.this_month)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.me)

    def dashboard(self, **params):
        response = self.client.get('/api/crm/dashboard/', {'owner': self.me.pk, **params})
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def months(self, rows):
        return {row['month']: row['total'] for row in rows}

    # ---- the card -------------------------------------------------------
    def test_closed_lost_total_and_count(self):
        self.deal(self.lost_stage, amount='1000')
        self.deal(self.lost_stage, amount='2500.50')
        self.deal(self.lost_stage, amount=None)                       # counted, adds nothing
        data = self.dashboard()
        self.assertEqual(Decimal(str(data['closed_lost']['total'])), Decimal('3500.50'))
        self.assertEqual(data['closed_lost']['count'], 3)

    def test_won_and_open_deals_do_not_leak_into_lost(self):
        self.deal(self.lost_stage, amount='100')
        self.deal(self.won_stage, amount='999')
        self.deal(self.open_stage, amount='888')
        data = self.dashboard()
        self.assertEqual((Decimal(str(data['closed_lost']['total'])), data['closed_lost']['count']), (Decimal('100'), 1))
        self.assertEqual((Decimal(str(data['closed_won']['total'])), data['closed_won']['count']), (Decimal('999'), 1))

    def test_nothing_lost_is_zero_not_missing(self):
        data = self.dashboard()
        self.assertEqual(data['closed_lost'], {'total': 0, 'count': 0})
        self.assertEqual(len(data['my_monthly_closed_lost']), 12)
        self.assertTrue(all(row['total'] == 0 for row in data['my_monthly_closed_lost']))

    def test_only_the_selected_owner(self):
        self.deal(self.lost_stage, amount='100')
        self.deal(self.lost_stage, owner=self.other, amount='5000')
        self.assertEqual(Decimal(str(self.dashboard()['closed_lost']['total'])), Decimal('100'))
        everyone = self.client.get('/api/crm/dashboard/').json()               # no owner = all users
        self.assertGreaterEqual(Decimal(str(everyone['closed_lost']['total'])), Decimal('5100'))

    # ---- total deals (the base for the % of total) -------------------------
    def test_total_deals_counts_open_won_and_lost_of_the_owner(self):
        self.deal(self.open_stage)
        self.deal(self.open_stage)
        self.deal(self.won_stage)
        self.deal(self.lost_stage)
        self.deal(self.lost_stage, owner=self.other)                    # someone else's deal
        data = self.dashboard()
        self.assertEqual(data['total_deals'], 4)
        self.assertEqual((data['closed_won']['count'], data['closed_lost']['count']), (1, 1))

    def test_the_total_is_open_plus_won_plus_lost(self):
        for stage in (self.open_stage, self.open_stage, self.open_stage, self.won_stage, self.won_stage,
                      self.lost_stage):
            self.deal(stage)
        data = self.dashboard()
        self.assertEqual(data['deal_breakdown'], {'open': 3, 'won': 2, 'lost': 1})
        self.assertEqual(data['total_deals'], 6)
        # and for everyone, on the real data too
        everyone = self.client.get('/api/crm/dashboard/').json()
        parts = everyone['deal_breakdown']
        self.assertEqual(parts['open'] + parts['won'] + parts['lost'], everyone['total_deals'])

    def test_total_deals_is_not_cut_by_the_date_range(self):
        self.deal(self.open_stage, closed=None)
        self.deal(self.lost_stage, closed=datetime.date(2026, 5, 10))
        self.deal(self.won_stage, closed=datetime.date(2026, 6, 20))
        data = self.dashboard(closing_date_after='2026-06-01', closing_date_before='2026-06-30')
        self.assertEqual(data['total_deals'], 3)
        self.assertEqual((data['closed_won']['count'], data['closed_lost']['count']), (1, 0))

    def test_total_deals_for_all_users_is_everything(self):
        self.deal(self.lost_stage)
        self.deal(self.lost_stage, owner=self.other)
        everyone = self.client.get('/api/crm/dashboard/').json()
        self.assertEqual(everyone['total_deals'], Deal.objects.count())
        self.assertGreaterEqual(everyone['total_deals'], 2)

    # ---- the date range -------------------------------------------------
    def test_the_closing_date_range_applies_to_lost_and_won_alike(self):
        early, late = datetime.date(2026, 5, 10), datetime.date(2026, 6, 20)
        self.deal(self.lost_stage, amount='100', closed=early)
        self.deal(self.lost_stage, amount='200', closed=late)
        self.deal(self.won_stage, amount='7', closed=early)
        self.deal(self.won_stage, amount='9', closed=late)
        data = self.dashboard(closing_date_after='2026-06-01', closing_date_before='2026-06-30')
        self.assertEqual((Decimal(str(data['closed_lost']['total'])), data['closed_lost']['count']), (Decimal('200'), 1))
        self.assertEqual((Decimal(str(data['closed_won']['total'])), data['closed_won']['count']), (Decimal('9'), 1))
        data = self.dashboard(closing_date_before='2026-05-31')
        self.assertEqual((Decimal(str(data['closed_lost']['total'])), data['closed_lost']['count']), (Decimal('100'), 1))

    # ---- the last-12-months chart ----------------------------------------
    def test_monthly_lost_chart_places_amounts_in_the_right_months(self):
        self.deal(self.lost_stage, amount='100', closed=self.this_month)
        self.deal(self.lost_stage, amount='50', closed=self.this_month)
        self.deal(self.lost_stage, amount='400', closed=self.two_months_ago)
        self.deal(self.lost_stage, amount='9999', closed=self.too_old)          # outside the 12 months
        rows = self.dashboard()['my_monthly_closed_lost']
        self.assertEqual(len(rows), 12)
        self.assertEqual(rows[-1]['month'], self.month_start.strftime('%b'))
        self.assertEqual(Decimal(str(rows[-1]['total'])), Decimal('150'))
        self.assertEqual(Decimal(str(rows[-3]['total'])), Decimal('400'))
        self.assertEqual(Decimal(str(sum(r['total'] for r in rows))), Decimal('550'))

    def test_the_monthly_charts_keep_won_and_lost_apart(self):
        self.deal(self.lost_stage, amount='111')
        self.deal(self.won_stage, amount='222')
        data = self.dashboard()
        self.assertEqual(Decimal(str(data['my_monthly_closed_lost'][-1]['total'])), Decimal('111'))
        self.assertEqual(Decimal(str(data['my_monthly_closed_won'][-1]['total'])), Decimal('222'))

    def test_the_won_chart_is_unchanged_in_shape(self):
        rows = self.dashboard()['my_monthly_closed_won']
        self.assertEqual(len(rows), 12)
        self.assertEqual(set(rows[0]), {'month', 'total'})
