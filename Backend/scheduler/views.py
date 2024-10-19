import os
import openai
import requests
import re
import calendar
from datetime import datetime, timedelta
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from dotenv import load_dotenv

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view

from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.contrib.auth import login as django_login, logout as django_logout
from django.contrib.auth.decorators import login_required

from .models import Task
from .models import UserProfile
from datetime import datetime


load_dotenv()
openai.api_key = os.getenv('OPENAI_API_KEY')
openweather_api_key = os.getenv('OPENWEATHER_API_KEY')

# Register View
@api_view(['POST'])
def register(request):
    username = request.data.get('username')
    email = request.data.get('email')
    password = request.data.get('password')

    if User.objects.filter(username=username).exists():
        return Response({"error": "Username already exists."}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(email=email).exists():
        return Response({"error": "Email already exists."}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.create_user(username=username, email=email, password=password)
    user.save()

    return Response({"message": "User registered successfully!"}, status=status.HTTP_201_CREATED)

@api_view(['POST'])
def login(request):
    username = request.data.get('username')
    password = request.data.get('password')

    user = authenticate(username=username, password=password)
    if user is not None:
        django_login(request, user)
        return Response({"message": "Login successful!"}, status=status.HTTP_200_OK)
    else:
        return Response({"error": "Invalid credentials."}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def logout(request):
    django_logout(request)
    return Response({"message": "Logged out successfully!"}, status=status.HTTP_200_OK)
    
@csrf_exempt
@login_required
def create_task(request):
    if request.method == "POST":
        data = json.loads(request.body)
        task_info = data.get('task_info', [])

        if len(task_info) != 4 or not isinstance(task_info[0], str) or not isinstance(task_info[1], bool):
            return JsonResponse({"error": "Invalid task data. Expected a description string, boolean for is_complete, date string, and time string."}, status=400)

        task_description = task_info[0]
        is_complete = task_info[1]
        task_date_str = task_info[2]  
        task_time_str = task_info[3]
        task_date = None
        task_time = None

        if task_date_str:
            try:
                # Parsing date in format like "Oct 11, 2024"
                task_date = datetime.strptime(task_date_str, "%b %d, %Y").date()
            except ValueError:
                return JsonResponse({"error": "Invalid date format"}, status=400)

        if task_time_str:
            try:
                # Parsing time in format like "12:00 AM"
                task_time = datetime.strptime(task_time_str, "%I:%M %p").time()
            except ValueError:
                return JsonResponse({"error": "Invalid time format"}, status=400)

        # Save the task for the currently logged-in user
        task = Task.objects.create(
            user=request.user,
            task_description=task_description,
            is_complete=is_complete,
            task_date=task_date,
            task_time=task_time
        )
        task.save()

        return JsonResponse({"message": "Task created successfully!"}, status=201)

@login_required
def list_task(request):
    if request.method == "GET":
        tasks = Task.objects.filter(user=request.user)

        task_list = [{
            "id": task.id,
            "task_description": task.task_description,
            "is_complete": task.is_complete,
            "task_date": task.task_date.strftime("%b %d, %Y") if task.task_date else None,
            "task_time": task.task_time.strftime("%I:%M %p") if task.task_time else None,
            "weather": task.weather
        } for task in tasks]

        return JsonResponse({"tasks": task_list}, status=200)

    return JsonResponse({"error": "Invalid request method."}, status=400)

@csrf_exempt
@login_required
def delete_task(request, task_id):
    if request.method == "DELETE":
            task = Task.objects.get(id=task_id, user=request.user)
            task.delete()
            return JsonResponse({"message": "Task deleted successfully!"}, status=200)
    return JsonResponse({"error": "Invalid request method."}, status=400)

# Helper function to get latitudes and longitudes based on city using OpenWeather Geocoding API
def get_lat_lon_openweather(api_key, city, state):
    # Combine city and state for the query
    location = f"{city},{state}"
    country = "ISO 3166"
    geocode_url = f"http://api.openweathermap.org/geo/1.0/direct?q={city},{state},{country}&limit=1&appid={api_key}"
    response = requests.get(geocode_url)
    
    if response.status_code == 200:
        data = response.json()
        if data:
            lat = data[0]['lat']
            lon = data[0]['lon']
            return lat, lon
        else:
            return None, None
    else:
        return None, None

@login_required
def save_user_location(request):
    if request.method == "POST":
        data = json.loads(request.body)
        city = data.get('city')
        state = data.get('state')

        if city is None or state is None:
            return JsonResponse({"error": "City and State names are required."}, status=400)

        # Use the city and state name to get lat and lon via OpenWeather API
        lat, lon = get_lat_lon_openweather(openweather_api_key, city, state)

        if lat is None or lon is None:
            return JsonResponse({"error": "Could not retrieve coordinates for the provided location."}, status=400)

        # Create or update user profile with location
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        profile.latitude = lat
        profile.longitude = lon
        profile.save()

        return JsonResponse({"message": "Location saved successfully!"}, status=200)
    


@login_required
def process_command(request):
    if request.method == "POST":
        data = json.loads(request.body)
        command = data.get('command')
        if not command:
            return JsonResponse({"error": "Command not provided."}, status=400)

        # Fetch the user's saved location (lat, lon) from the UserProfile model
        try:
            profile = UserProfile.objects.get(user=request.user)
            lat, lon = profile.latitude, profile.longitude
        except UserProfile.DoesNotExist:
            return JsonResponse({"error": "Location not found. Please update your location first."}, status=400)

        # If lat/lon are not saved, return an error
        if lat is None or lon is None:
            return JsonResponse({"error": "Latitude and longitude are not set. Please update your location."}, status=400)

        # Interpret the command using OpenAI API
        interpreted_info = interpret_command(command)

        match_task = re.search(r'Task: (\w+)', interpreted_info)
        if match_task:
            task_description = match_task.group(1)

        match_time = re.search(r'(\d{1,2}:\d{2} [apAP][mM])', interpreted_info)  # Time
        time_text = match_time.group(1) if match_time else "12:00 PM"
        
        match_date = re.search(r'(today|tomorrow|next \w+|\d+ days later|\d{4}-\d{2}-\d{2})', interpreted_info)
        date_text = match_date.group(1) if match_date else None  

        if date_text is None:
            return JsonResponse({"error": "Sorry, I couldn't understand the date."})

        # Convert extracted date and time 
        reminder_time = calculate_datetime(date_text, time_text)
        if reminder_time is None:
            return JsonResponse({"error": "Sorry, I couldn't understand the date or time."})

        # Get weather information using lat and lon
        weather_info = get_weather(openweather_api_key, lat, lon, reminder_time)
        weather_short_description = extract_weather_description(weather_info)

        print("Weather intepreted: ", weather_short_description)

        # Save the task to the database
        task = Task.objects.create(
            user=request.user,
            task_description=task_description,
            is_complete=False,  
            task_date=reminder_time.date(),
            task_time=reminder_time.time(),
            weather = weather_short_description
        )
        task.save()

        # Generate the response
        response = f"Sure, we set you a reminder for {reminder_time.strftime('%I:%M %p on %A')}. {weather_info}"

        return JsonResponse({"response": response})

    return JsonResponse({"error": "Invalid request method."})

def extract_weather_description(full_weather_info):
    # Extract the part that contains only the weather and temperature from the full response.
    # Assuming the format is like: "The weather at 02:00 PM on Friday will be light rain with a temperature of 9.5°C (49.0°F)"
    # Return: "light rain, 9.5°C (49.0°F)."
    
    match = re.search(r'will be (.+) with a temperature of ([\d\.]+°C \([\d\.]+°F\))', full_weather_info)
    if match:
        weather_description = match.group(1)
        temperature = match.group(2)
        return f"{weather_description}, {temperature}"
    return full_weather_info

# Interpret commands 
def interpret_command(command):
    prompt = f"""
    You are an intelligent assistant that helps users schedule tasks. The user will provide a scheduling command like "Set a reminder for 3pm tomorrow" or "Schedule an appointment next Tuesday at 4pm."
    
    Your task is to extract:
    - Task: What the user wants to schedule (e.g., reminder, meeting, appointment, cinema, doctor, school). If user doesn't provide task, go with default task which is "reminder".
    - Date: The date of the event (phrases like "tomorrow", "next Tuesday", or specific dates like "2024-09-28").
    - Time: The time of the event (if not provided, assume 12:00 PM).
    
    Example output:
    Task: reminder
    Date: tomorrow
    Time: 3:00 PM
    
    Here is the user’s command: "{command}"

    Please provide the response in this format:
    Task: [task]
    Date: [date]
    Time: [time]
    """

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an assistant."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=150,
        temperature=0.5
    )

    return response['choices'][0]['message']['content'].strip()


# Helper function to retrieve weather data from OpenWeather API
def get_weather(api_key, lat, lon, reminder_time):
    # One Call API 3.0 URL 
    url = f"https://api.openweathermap.org/data/3.0/onecall?lat={lat}&lon={lon}&exclude=minutely,alerts&appid={api_key}&units=metric"
    
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()

        # Find the closest hourly forecast to the reminder time (within 1 hour)
        closest_forecast = None
        min_time_diff = float('inf')

        for forecast in data['hourly']:
            forecast_time = datetime.fromtimestamp(forecast['dt'])
            
            # Calculate time difference in seconds
            time_diff = abs((forecast_time - reminder_time).total_seconds())
            
            # Check for the closest forecast within 1 hour (3600 seconds)
            if time_diff <= 3600:
                if time_diff < min_time_diff:
                    min_time_diff = time_diff
                    closest_forecast = forecast
        
        if closest_forecast:
            # Get temperature and weather description from the closest forecast
            temp_celsius = closest_forecast['temp']
            temp_fahrenheit = (temp_celsius * 9/5) + 32  # Convert to Fahrenheit
            weather_description = closest_forecast['weather'][0]['description']
            
            return (f"The weather at {reminder_time.strftime('%I:%M %p')} on {reminder_time.strftime('%A')} will be "
                    f"{weather_description} with a temperature of {temp_celsius:.1f}°C ({temp_fahrenheit:.1f}°F).")
        
        return "No specific weather data available for the closest time."
    else:
        return "Failed to retrieve weather data."

# Helper function to calculate date and time
def calculate_datetime(date_text, time_text="12:00 PM"):
    try:
        
        # Convert "3pm" or "3 PM" to "3:00 PM"
        time_text = re.sub(r'(\d{1,2})([apAP][mM])', r'\1:00 \2', time_text.strip())  
        
        # format AM/PM
        time = datetime.strptime(time_text, "%I:%M %p").time()

        # Handle the date text logic
        if "tomorrow" in date_text.lower():
            date = datetime.now() + timedelta(days=1)
        elif "today" in date_text.lower():
            date = datetime.now()
        elif "next" in date_text.lower():
            match = re.search(r'next (\w+)', date_text)
            if match:
                day_of_week = match.group(1).capitalize()
                today = datetime.now()
                target_weekday = list(calendar.day_name).index(day_of_week)  # Convert to weekday index
                days_ahead = (target_weekday - today.weekday() + 7) % 7
                if days_ahead == 0:
                    days_ahead += 7  
                date = today + timedelta(days=days_ahead)
        elif "later" in date_text.lower():
            match = re.search(r'(\d+) days later', date_text)
            if match:
                days = int(match.group(1))
                date = datetime.now() + timedelta(days=days)
        else:
            # format "YYYY-MM-DD"
            date = datetime.strptime(date_text, "%Y-%m-%d")  

        # Combine the parsed date and time 
        return datetime.combine(date.date(), time)

    except Exception as e:
        print(f"Error parsing date and time: {e}")
        return None




