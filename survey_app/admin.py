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

class WebcamClipInline(admin.TabularInline):
    model = WebcamClip
    extra = 0
    readonly_fields = ("clip", "created_at")
    can_delete = False


class ScreenClipInline(admin.TabularInline):
    model = ScreenClip
    extra = 0
    readonly_fields = ("clip", "created_at")
    can_delete = False


@admin.register(ParticipantSession)
class ParticipantSessionAdmin(admin.ModelAdmin):
    inlines = [WebcamClipInline, ScreenClipInline]


admin.site.register(Movie)
admin.site.register(Review)
admin.site.register(MovieSelection)
admin.site.register(MovieReviewResponse)


@admin.register(WebcamClip)
class WebcamClipAdmin(admin.ModelAdmin):
    list_display = ("id", "participant", "clip", "created_at")
    list_select_related = ("participant",)
    list_filter = ("created_at",)
    search_fields = ("participant__id", "participant__user__username", "clip")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)


@admin.register(ScreenClip)
class ScreenClipAdmin(admin.ModelAdmin):
    list_display = ("id", "participant", "clip", "created_at")
    list_select_related = ("participant",)
    list_filter = ("created_at",)
    search_fields = ("participant__id", "participant__user__username", "clip")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)


@admin.register(PaasResponse)
class PaasResponseAdmin(admin.ModelAdmin):
    list_display = ('participant', 'task_number', 'rating', 'created_at')