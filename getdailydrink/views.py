from django.shortcuts import redirect, render
from django.http import JsonResponse
import pandas as pd
from accounts.models import Profile
from .forms import *
from .models import UserWaterIntake, SaveGoal, WaterTake
from django.contrib.auth.decorators import login_required
from django.utils.timezone import now
import numpy as np
from django.contrib import messages
from django.http import HttpResponse
import joblib
from datetime import timedelta

model = joblib.load('hydration_model.pkl')


def email_save(request):
    if request.method == 'POST':
        form = EmailSupport(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'We will give you the last new of App.')
        else:
            print(form.errors)
    else:
        form = EmailSupport()
    return redirect('home')

def home(request):

    """ Displays reward leaderboard based on points earned. """
    user = request.user
    if not request.session.session_key:
        request.session.create()

    # Show rewards to all users
    rewards = SaveGoal.objects.all().order_by('-points')
    winners = SaveGoal.objects.all().order_by('-points')[0:3]
    context = {
        'rewards': rewards,
        'winners' : winners,

        'water' : 0
    }
    if request.user.is_authenticated:
        dailygoal = UserWaterIntake.objects.filter(user=user).last()
    else:
        dailygoal = UserWaterIntake.objects.filter(session_key=request.session.session_key).last()
    if dailygoal:
        context.update({
            'dailygoal' : dailygoal,
            'water': round(dailygoal.water_amount, 2),
        })
    if request.user.is_authenticated:
        return redirect('rankup')
    
    return render(request, 'pages/home.html', context)


def rankup_page(request):
    """ Home page: All users can see rewards and rankings """
    
    if not request.session.session_key:
        request.session.create()
        
    rewards = SaveGoal.objects.all().order_by('-points')
    winners = SaveGoal.objects.all().order_by('-points')[0:3]

    user = request.user if request.user.is_authenticated else None
    session_key = request.session.session_key

    # Fetch user's last daily goal
    if user:
        dailygoal = UserWaterIntake.objects.filter(user=user).last()
        # Get today's water intake
        today_intake = WaterTake.objects.filter(
            user=user, 
            created_at__date=now().date()
        )
        today_total = sum(entry.amount_liters for entry in today_intake)

        # Get this week's water intake
        week_intake = WaterTake.objects.filter(
            user=user,
            created_at__date__gte=now().date() - timedelta(days=7)
        )
        week_total = sum(entry.amount_liters for entry in week_intake)

        # Get this month's water intake
        month_intake = WaterTake.objects.filter(
            user=user,
            created_at__date__gte=now().date() - timedelta(days=30)
        )
        month_total = sum(entry.amount_liters for entry in month_intake)

        # Calculate weekly and monthly goals
        weekly_goal = dailygoal.water_amount * 7 if dailygoal else 0
        monthly_goal = dailygoal.water_amount * 30 if dailygoal else 0

        recap_data = {
            'today_total': round(today_total, 1),
            'today_goal': round(dailygoal.water_amount if dailygoal else 0, 1),
            'week_total': round(week_total, 1),
            'week_goal': round(weekly_goal, 1),
            'month_total': round(month_total, 1),
            'month_goal': round(monthly_goal, 1),
        }
    else:
        dailygoal = UserWaterIntake.objects.filter(session_key=session_key).last()
        recap_data = None
    
    if not dailygoal:
        messages.error(request, "Please set a daily water goal first!")
        return redirect('log_water')

    # For non-authenticated users, show rewards and rankings but hide water logging
    if not request.user.is_authenticated:
        context = {
            'winners': winners,
            'dailygoal' : dailygoal,
            'rewards': rewards,
            'water': round(dailygoal.water_amount, 2),
            'recap_data': recap_data
        }
        return render(request, 'pages/rankup.html', context)

    # Fetch logged-in user's water intake
    water_intake = WaterTake.objects.filter(user=user, created_at__date=now().date())
    total_intake = sum(entry.amount_liters for entry in water_intake)

    if request.method == 'POST':
        form = GoalWaterForm(request.POST)
        if form.is_valid():
            cup_sizes = {"250ml": 0.25, "500ml": 0.5, "1L": 1.0}
            cup = form.cleaned_data['cup']
            amount_liters = cup_sizes.get(cup, 0)

            if amount_liters == 0:
                messages.error(request, "Invalid cup size.")
                return redirect('rankup')

            # Save water intake
            WaterTake.objects.create(user=user, cup=cup, amount_liters=amount_liters)
            total_intake += amount_liters

            # Get or create SaveGoal
            savegoal, _ = SaveGoal.objects.get_or_create(
                user=user, 
                defaults={"water_intake": dailygoal}
            )
            
            # Check if goal is complete
            if total_intake >= dailygoal.water_amount:
                savegoal.complete = True
                savegoal.points += 5
                savegoal.water_intake = dailygoal
                savegoal.save()

                messages.success(request, f"Goal completed! 🎉 You earned {savegoal.points} points.")
                return redirect('rankup')

    else:
        form = GoalWaterForm()

    water_left = max(dailygoal.water_amount - total_intake, 0)

    context = {
        'form': form, 
        'winners' : winners,
        'rewards': rewards,
        'water': round(dailygoal.water_amount, 2),
        'water_left': round(water_left, 2),
        'recap_data': recap_data,
    }
    return render(request, 'pages/rankup.html', context)
def log_water(request):
    """Logs user's water intake goal based on ML prediction."""
    
    # Load the trained model (ensure it's available)
    try:
        model = joblib.load('hydration_model.pkl')  # Load your trained model
    except FileNotFoundError:
        print("Model file not found!")
        # Handle the error by returning an appropriate response
        return render(request, 'error_page.html', {'message': 'Model file not found.'})

    profile = None

    if request.user.is_authenticated:
        try:
            profile = request.user.profile
        except Profile.DoesNotExist:
            profile = None
    
    if request.method == 'POST':
        form = WaterIntakeForm(request.POST)
        if form.is_valid():
            try:
                # Extract profile data (fixed)
                if profile:
                    weight = profile.weight
                    gender = profile.gender  # Keep gender as a string ('male' or 'female')
                    age = profile.age
                else:
                    weight = form.cleaned_data['weight']
                    gender = form.cleaned_data['gender']  # Keep gender as a string
                    age = form.cleaned_data['age']

                # Extract form data
                climate = form.cleaned_data['climate']  # 'cold', 'temperate', or 'hot' as string
                activity_level = form.cleaned_data['activity_level']  # 'sedentary', 'lightly-active', etc., as string
                health_conditions = form.cleaned_data['health_conditions']  # 'none', 'diabetes', etc., as string

                # Prepare input data for prediction (using numeric mappings)
                climate_map = {'cold': 0, 'temperate': 1, 'hot': 2}
                activity_level_map = {'sedentary': 0, 'lightly-active': 1, 'moderately-active': 2, 'very-active': 3}
                health_conditions_map = {'none': 0, 'diabetes': 1, 'kidney disease': 2, 'heart disease': 3, 'pregnancy': 4}

                input_data = np.array(
                    [[
                    weight, 
                    0 if gender == 'male' else 1,  # gender as integer (0 or 1)
                    climate_map[climate], 
                    activity_level_map[activity_level], 
                    age, 
                    health_conditions_map[health_conditions]
                    ]], 
                    dtype=np.float32
                )
                
                columns = ['weight', 'gender', 'climate', 'activity_level', 'age', 'health_conditions']
                input_df = pd.DataFrame(input_data, columns=columns)

                # Perform the prediction
                predicted_water = model.predict(input_df)[0]

                # Save new data entry into CSV (store string representations in the CSV)
                new_entry = pd.DataFrame([{
                    'gender': gender,  # Save as string ('male' or 'female')
                    'age': age,
                    'weight': weight,
                    'climate': climate,  # Save as string ('cold', 'temperate', etc.)
                    'health_conditions': health_conditions,  # Save as string
                    'activity_level': activity_level,  # Save as string
                }])
                new_entry.to_csv('hydration_data.csv', mode='a', header=False, index=False)

                # Ensure session is created
                if not request.session.session_key:
                    request.session.create()

                # Save the prediction to the database
                if request.user.is_authenticated:
                    UserWaterIntake.objects.create(
                        user=request.user,
                        water_amount=predicted_water,
                        email_frequency=form.cleaned_data['email_frequency']
                    )
                else:
                    UserWaterIntake.objects.create(
                        session_key=request.session.session_key,
                        water_amount=predicted_water,
                        email_frequency=form.cleaned_data['email_frequency']
                    )

                return redirect('home')
            except Exception as e:
                messages.error(request, f"Error processing your request: {str(e)}")
        else:
            messages.error(request, "Please correct the errors in the form.")
            print("Form Errors:", form.errors)  # Debugging

    else:
        form = WaterIntakeForm()

    return render(request, 'pages/log_water.html', {'form': form})

def user_profile(request):
    return render(request, 'pages/profile.html')
