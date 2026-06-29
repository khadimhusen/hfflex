import math
from django.db import models

class MixedInk(models.Model):
    qty = models.DecimalField(max_digits=5, decimal_places=3, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # LAB - No White (ink only on polyester)
    l_nw = models.DecimalField(max_digits=6, decimal_places=2)
    a_nw = models.DecimalField(max_digits=6, decimal_places=2)
    b_nw = models.DecimalField(max_digits=6, decimal_places=2)

    # LAB - With White (white backup)
    l_ww = models.DecimalField(max_digits=6, decimal_places=2)
    a_ww = models.DecimalField(max_digits=6, decimal_places=2)
    b_ww = models.DecimalField(max_digits=6, decimal_places=2)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"Ink Can #{self.id}"

    @property
    def delta_nw_ww(self):

        """ delta with white and without white."""
        return round(math.sqrt(
            (float(self.l_nw) - float(self.l_ww)) ** 2 +
            (float(self.a_nw) - float(self.a_ww)) ** 2 +
            (float(self.b_nw) - float(self.b_ww)) ** 2
        ),0)




