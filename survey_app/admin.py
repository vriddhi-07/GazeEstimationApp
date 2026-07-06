from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

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


def _clip_preview(clip_obj, kind: str):
    if not clip_obj.clip:
        return "(no file)"
    download_url = reverse("survey_app:download_clip", args=[kind, clip_obj.id])
    return format_html(
        '<video src="{}" controls preload="metadata" style="max-width: 320px; max-height: 200px; display: block; margin-bottom: 4px;"></video>'
        '<a href="{}">Download {}</a>',
        clip_obj.clip.url,
        download_url,
        clip_obj.clip.name.rsplit("/", 1)[-1],
    )


class WebcamClipInline(admin.TabularInline):
    model = WebcamClip
    extra = 0
    readonly_fields = ("clip_preview", "created_at")
    fields = ("clip_preview", "created_at")
    can_delete = False

    def clip_preview(self, obj):
        return _clip_preview(obj, "webcam")
    clip_preview.short_description = "Clip"


class ScreenClipInline(admin.TabularInline):
    model = ScreenClip
    extra = 0
    readonly_fields = ("clip_preview", "created_at")
    fields = ("clip_preview", "created_at")
    can_delete = False

    def clip_preview(self, obj):
        return _clip_preview(obj, "screen")
    clip_preview.short_description = "Clip"


@admin.register(ParticipantSession)
class ParticipantSessionAdmin(admin.ModelAdmin):
    inlines = [WebcamClipInline, ScreenClipInline]


admin.site.register(Movie)
admin.site.register(Review)
admin.site.register(MovieSelection)
admin.site.register(MovieReviewResponse)


@admin.register(WebcamClip)
class WebcamClipAdmin(admin.ModelAdmin):
    list_display = ("id", "participant", "clip_download_link", "created_at")
    list_select_related = ("participant",)
    list_filter = ("created_at",)
    search_fields = ("participant__id", "participant__user__username", "clip")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "clip_preview")
    fields = ("participant", "clip_preview", "created_at")

    def clip_preview(self, obj):
        return _clip_preview(obj, "webcam")
    clip_preview.short_description = "Clip"

    def clip_download_link(self, obj):
        if not obj.clip:
            return "(no file)"
        download_url = reverse("survey_app:download_clip", args=["webcam", obj.id])
        return format_html('<a href="{}">Download</a>', download_url)
    clip_download_link.short_description = "Clip"


@admin.register(ScreenClip)
class ScreenClipAdmin(admin.ModelAdmin):
    list_display = ("id", "participant", "clip_download_link", "created_at")
    list_select_related = ("participant",)
    list_filter = ("created_at",)
    search_fields = ("participant__id", "participant__user__username", "clip")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "clip_preview")
    fields = ("participant", "clip_preview", "created_at")

    def clip_preview(self, obj):
        return _clip_preview(obj, "screen")
    clip_preview.short_description = "Clip"

    def clip_download_link(self, obj):
        if not obj.clip:
            return "(no file)"
        download_url = reverse("survey_app:download_clip", args=["screen", obj.id])
        return format_html('<a href="{}">Download</a>', download_url)
    clip_download_link.short_description = "Clip"


@admin.register(PaasResponse)
class PaasResponseAdmin(admin.ModelAdmin):
    list_display = ('participant', 'task_number', 'rating', 'created_at')