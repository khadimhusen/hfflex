"""The "blank" box of the cylinder filter on the process lists."""
import django_filters
from django.test import TestCase

from customer.models import Customer
from itemmaster.models import ItemMaster
from order.filters import BlankableMultipleChoiceFilter, JobProcessFilter, JobProcessFilter1
from order.choices import cylinderchoices
from order.models import JobProcess


class ItemFilter(django_filters.FilterSet):
    """The same filter on the item itself, where the cylinder status lives."""
    cylinder = BlankableMultipleChoiceFilter(field_name='cylinder_status', choices=cylinderchoices)

    class Meta:
        model = ItemMaster
        fields = []


class BlankCylinderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        customer = Customer.objects.create(name='TEST CYLFILTER CUSTOMER')
        cls.by_status = {}
        for name, status in (('none', None), ('empty', ''), ('available', 'Available'),
                             ('notapplicable', 'Not Applicable'), ('notavailable', 'Not Available')):
            cls.by_status[name] = ItemMaster.objects.create(
                itemname=f'TESTCYL {name}', itemcustomer=customer, cylinder_status=status)

    def found(self, *values):
        qs = ItemMaster.objects.filter(itemname__startswith='TESTCYL ')
        data = {'cylinder': list(values)} if values else {}
        filterset = ItemFilter(data, queryset=qs)
        self.assertTrue(filterset.form.is_valid(), filterset.form.errors)
        return {i.itemname.split(' ')[1].lower() for i in filterset.qs}

    def test_blank_alone_finds_items_with_no_status(self):
        self.assertEqual(self.found(''), {'none', 'empty'})

    def test_blank_with_another_choice(self):
        self.assertEqual(self.found('', 'Not Applicable'), {'none', 'empty', 'notapplicable'})

    def test_the_other_choices_still_work(self):
        self.assertEqual(self.found('Available'), {'available'})
        self.assertEqual(self.found('Available', 'Not Available'), {'available', 'notavailable'})

    def test_nothing_ticked_filters_nothing(self):
        self.assertEqual(self.found(), set(self.by_status))


class BothProcessFiltersAcceptBlank(TestCase):
    def check(self, filter_class):
        data = {'cylinder': ['', 'Not Applicable'], 'status': ['Pending', 'Incomplete']}
        filterset = filter_class(data, queryset=JobProcess.objects.all())
        self.assertTrue(filterset.form.is_valid(), filterset.form.errors)        # was: "not one of the available choices"
        sql = str(filterset.qs.query)
        self.assertIn('"cylinder_status" IS NULL', sql)
        self.assertIn("Not Applicable", sql)

    def test_the_process_list_filter(self):
        self.check(JobProcessFilter)

    def test_the_other_process_filter(self):
        self.check(JobProcessFilter1)

    def test_blank_stays_ticked_in_the_form(self):
        form = JobProcessFilter({'cylinder': ['', 'Not Applicable']}, queryset=JobProcess.objects.none()).form
        ticked = {str(box.data['value']) for box in form['cylinder'].subwidgets if box.data['selected']}
        self.assertEqual(ticked, {'', 'Not Applicable'})
