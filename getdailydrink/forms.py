from django import forms
from accounts.models import Profile
from .models import Email, UserWaterIntake, SaveGoal, WaterTake


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ('gender', 'age', 'weight', )

from django import forms

class WaterIntakeForm(forms.Form):
    gender = forms.ChoiceField(
        choices=[('male', 'Male'), ('female', 'Female')], 
        required=False,
        widget=forms.Select(attrs={'class': 'custom-select'}) 
    )
    age = forms.IntegerField(min_value=1, max_value=120, required=False)
    weight = forms.IntegerField(min_value=1, max_value=300, required=False)
    activity_level = forms.ChoiceField(
        choices=[ 
            ('sedentary', 'Sedentary'),
            ('lightly-active', 'Lightly Active'),
            ('moderately-active', 'Moderately Active'),
            ('very-active', 'Very Active')
        ], 
        required=True,
        widget=forms.Select(attrs={'class': 'custom-select'}) 
    )
    climate = forms.ChoiceField(
        choices=[('cold', 'Cold'), ('temperate', 'Temperate'), ('hot', 'Hot')], 
        required=True,
        widget=forms.Select(attrs={'class': 'custom-select'}) 
    )
    health_conditions = forms.ChoiceField(
        choices=[ 
            ('none', 'None'),
            ("pregnancy", "Pregnancy"),
            ("diabetes", "Diabetes"),
            ("kidney disease", "Kidney Disease"),
            ("heart disease", "Heart Disease")
        ], 
        required=False,
        widget=forms.Select(attrs={'class': 'custom-select'}) 
    )
    email_frequency = forms.ChoiceField(
        choices=[
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
        ],
        widget=forms.Select(attrs={'class': 'custom-select'}) ,
        required=False,
    )
    reminder_times = forms.MultipleChoiceField(
        choices=[(str(hour), f"{hour}:00") for hour in range(24)],
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'custom-checkbox'}),
        required=False,
    )

    # Custom widget updates
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in ['activity_level', 'climate', 'health_conditions']:
            self.fields[field].widget.attrs.update({'class': 'border border-gray-500 text-black'})


class GoalWaterForm(forms.ModelForm):
    class Meta:
        model = WaterTake
        fields = ['cup']


class EmailSupport(forms.ModelForm):
    class Meta:
        model = Email
        fields = '__all__'
        