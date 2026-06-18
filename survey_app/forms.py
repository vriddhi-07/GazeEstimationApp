from django import forms


EDUCATION_LEVEL_CHOICES = [
    ("high_school", "High school"),
    ("diploma", "Diploma"),
    ("bachelors", "Bachelor's degree"),
    ("masters", "Master's degree"),
    ("doctorate", "Doctorate"),
    ("other", "Other"),
]

GENDER_CHOICES = [
    ("female", "Female"),
    ("male", "Male"),
    ("non_binary", "Non-binary"),
    ("prefer_not_to_say", "Prefer not to say"),
    ("self_describe", "Self-describe"),
]

WORDS_READ_DAILY_CHOICES = [
    ("under_500", "Under 500 words"),
    ("500_1000", "500 to 1,000 words"),
    ("1000_3000", "1,000 to 3,000 words"),
    ("3000_5000", "3,000 to 5,000 words"),
    ("over_5000", "More than 5,000 words"),
]

MOVIES_PER_WEEK_CHOICES = [
    ("0", "0"),
    ("1", "1"),
    ("2_3", "2 to 3"),
    ("4_5", "4 to 5"),
    ("6_plus", "6 or more"),
]

AGREEMENT_CHOICES = [
    ("strongly_agree", "Strongly agree"),
    ("agree", "Agree"),
    ("neutral", "Neither agree nor disagree"),
    ("disagree", "Disagree"),
    ("strongly_disagree", "Strongly disagree"),
]

PROFESSION_CHOICES = [
    ("", "Select profession"),
    ("student", "Student"),
    ("faculty", "Faculty"),
    ("non-teaching staff", "Non-Teaching Staff"),
    ("not affiliated", "Not Affiliated"),
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


class ReadingHabitsForm(forms.Form):
    reads_words_daily = forms.ChoiceField(
        choices=WORDS_READ_DAILY_CHOICES,
        widget=forms.RadioSelect,
        label="How many words do you read every day?",
    )
    reads_news_daily = forms.ChoiceField(
        choices=[("yes", "Yes"), ("no", "No")],
        widget=forms.RadioSelect,
        label="Do you read news every day?",
    )
class MediaPreferencesForm(forms.Form):
    movies_per_week = forms.ChoiceField(
        choices=MOVIES_PER_WEEK_CHOICES,
        widget=forms.RadioSelect,
        label="How many movies do you watch in a typical week?",
    )
    picture_statement_agreement = forms.ChoiceField(
        choices=AGREEMENT_CHOICES,
        widget=forms.RadioSelect,
        label='“A picture is worth a thousand words.” Do you agree or disagree?',
    )

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