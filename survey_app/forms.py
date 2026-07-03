from django import forms


EDUCATION_LEVEL_CHOICES = [
    ("high_school", "High school"),
    ("diploma", "Diploma"),
    ("bachelors", "Bachelor's degree"),
    ("masters", "Master's degree"),
    ("doctorate", "Doctorate"),
    ("postdoctorate","Post-Doctorate")
    ("other", "Other"),
]

GENDER_CHOICES = [
    ("female", "Female"),
    ("male", "Male"),
    ("non_binary", "Non-binary"),
    ("prefer_not_to_say", "Prefer not to say"),
]

PROFESSION_CHOICES = [
    ("", "Select profession"),
    ("student", "Student"),
    ("faculty", "Faculty"),
    ("non-teaching staff", "Non-Teaching Staff"),
]

class ConsentForm(forms.Form):
    participant_tag = forms.CharField(
        max_length=64,
        required=False,
        label="Participant ID (optional)",
    )
    consent = forms.BooleanField(
        required=True,
        label=(
            "I understand that webcam and screen feed may be recorded during this survey "
            "for research purposes, and I consent to proceed."
        ),
    )


class DemographicForm(forms.Form):
    age = forms.IntegerField(min_value=1, max_value=120, label="Age")
    profession = forms.ChoiceField(choices=PROFESSION_CHOICES, label="Profession")
    education_level = forms.ChoiceField(
        choices=EDUCATION_LEVEL_CHOICES,
        label="Highest educational qualification",
    )
    gender = forms.ChoiceField(choices=GENDER_CHOICES, label="Gender")


from django import forms
 
class ExpertiseRatingForm(forms.Form):
    expertise_sentiment = forms.IntegerField(
        min_value=1, max_value=5, initial=1,
        widget=forms.NumberInput(attrs={"type": "range", "min": 1, "max": 5, "step": 1}),
    )
    expertise_fakenews = forms.IntegerField(
        min_value=1, max_value=5, initial=1,
        widget=forms.NumberInput(attrs={"type": "range", "min": 1, "max": 5, "step": 1}),
    )
    expertise_visualisation = forms.IntegerField(
        min_value=1, max_value=5, initial=1,
        widget=forms.NumberInput(attrs={"type": "range", "min": 1, "max": 5, "step": 1}),
    )