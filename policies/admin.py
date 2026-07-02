from django.contrib import admin

from .models import Department, Employe, PerformanceReview, RetentionOffer

admin.site.register(Department)
admin.site.register(Employe)
admin.site.register(PerformanceReview)
admin.site.register(RetentionOffer)
