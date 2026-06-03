from django.contrib import admin

from .models import (
    Movie,
    MovieReviewResponse,
    MovieSelection,
    ParticipantSession,
    Review,
    ScreenClip,
    WebcamClip,
    PaasResponse
)

admin.site.register(ParticipantSession)
admin.site.register(Movie)
admin.site.register(Review)
admin.site.register(MovieSelection)
admin.site.register(WebcamClip)
admin.site.register(ScreenClip)
admin.site.register(MovieReviewResponse)
@admin.register(PaasResponse)
class PaasResponseAdmin(admin.ModelAdmin):
    list_display = ('participant', 'task_number', 'rating', 'created_at')
