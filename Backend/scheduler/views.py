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

from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
from django.contrib.auth import authenticate

load_dotenv()
openai.api_key = os.getenv('OPENAI_API_KEY')
openweather_api_key = os.getenv('OPENWEATHER_API_KEY')
print(f"OpenAI API Key: {openai.api_key}")
print(f"OpenWeather API Key: {openweather_api_key}")

# Register View
@csrf_exempt
def register(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')

        if User.objects.filter(username=username).exists():
            return JsonResponse({"error": "Username already exists."}, status=400)
        
        if User.objects.filter(email=email).exists():
            return JsonResponse({"error": "Email already exists."}, status=400)

        user = User.objects.create_user(username=username, email=email, password=password)
        user.save()

        return JsonResponse({"message": "User registered successfully!"}, status=201)

@csrf_exempt
def login(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')

        user = authenticate(username=username, password=password)
        if user is not None:
            refresh = RefreshToken.for_user(user)
            return JsonResponse({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            })
        else:
            return JsonResponse({"error": "Invalid credentials."}, status=400)

# Helper function to get latitudes and longitudes based on city using OpenWeather Geocoding API
def get_lat_lon_openweather(api_key, city):
    geocode_url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={api_key}"
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

@csrf_exempt  # This disables CSRF protection for postman
def process_command(request):
    if request.method == "POST":
        command = request.POST.get('command')
        location = request.POST.get('location', 'your-default-city')

        # Use the OpenWeather Geocoding API to get lat and lon
        lat, lon = get_lat_lon_openweather(openweather_api_key, location)
        if lat is None or lon is None:
            return JsonResponse({"error": f"Could not find coordinates for the city: {location}"})

        # Interpret the command using GPT-4
        interpreted_info = interpret_command(command)

        # Print for debugging 
        print("Interpreted info:", interpreted_info)

        # Extract time and date from response
        match_time = re.search(r'(\d{1,2}:\d{2} [apAP][mM])', interpreted_info)  # Time
        time_text = match_time.group(1) if match_time else "12:00 PM"
        
        # Correctly handle "today" or "tomorrow" in the date
        match_date = re.search(r'(today|tomorrow|next \w+|\d+ days later|\d{4}-\d{2}-\d{2})', interpreted_info)
        date_text = match_date.group(1) if match_date else None  # No fallback to "tomorrow"
        
        if date_text is None:
            return JsonResponse({"error": "Sorry, I couldn't understand the date."})

        # Print for debugging 
        print("What is the date interpreted?:", date_text)

        # Convert extracted date and time to a Python datetime object
        reminder_time = calculate_datetime(date_text, time_text)

        if reminder_time is None:
            return JsonResponse({"error": "Sorry, I couldn't understand the date or time."})

        # Get weather information using lat and lon
        weather_info = get_weather(openweather_api_key, lat, lon, reminder_time)
        
        # Generate the response
        response = f"Sure, we set you a reminder for {reminder_time.strftime('%I:%M %p on %A')}. {weather_info}"
        return JsonResponse({"response": response})

    return JsonResponse({"error": "Invalid request method."})




# Interpret commands 
def interpret_command(command):
    prompt = f"""
    You are an intelligent assistant that helps users schedule tasks. The user will provide a scheduling command like "Set a reminder for 3pm tomorrow" or "Schedule an appointment next Tuesday at 4pm."
    
    Your task is to extract:
    - Task: What the user wants to schedule (e.g., reminder, meeting, appointment).
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
    # One Call API 3.0 URL with forecast for current, hourly, and daily data
    url = f"https://api.openweathermap.org/data/3.0/onecall?lat={lat}&lon={lon}&exclude=minutely,alerts&appid={api_key}&units=metric"
    
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()

        # Check hourly data to find exact time match for the reminder time
        for forecast in data['hourly']:
            forecast_time = datetime.fromtimestamp(forecast['dt'])
            
            # Match if the forecast time exactly equals the reminder time
            if forecast_time == reminder_time:
                temp_celsius = forecast['temp']  
                temp_fahrenheit = (temp_celsius * 9/5) + 32  # Convert to Fahrenheit
                weather_description = forecast['weather'][0]['description']
                
                return (f"The weather at {reminder_time.strftime('%I:%M %p')} on {reminder_time.strftime('%A')} will be "
                        f"{weather_description} with a temperature of {temp_celsius:.1f}°C ({temp_fahrenheit:.1f}°F).")
        
        return "No specific weather data available for the exact time."
    else:
        return "Failed to retrieve weather data."

# Helper function to calculate date and time
def calculate_datetime(date_text, time_text="12:00 PM"):
    try:
        
        # Convert "3pm" or "3 PM" to "3:00 PM"
        time_text = re.sub(r'(\d{1,2})([apAP][mM])', r'\1:00 \2', time_text.strip())  
        
        # correct format with a space before AM/PM
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
                    days_ahead += 7  # Make sure it's the next occurrence
                date = today + timedelta(days=days_ahead)
        elif "later" in date_text.lower():
            match = re.search(r'(\d+) days later', date_text)
            if match:
                days = int(match.group(1))
                date = datetime.now() + timedelta(days=days)
        else:
            # Attempt to parse a specific date in the form "YYYY-MM-DD"
            date = datetime.strptime(date_text, "%Y-%m-%d")  

        # Combine the parsed date and time into a datetime object
        return datetime.combine(date.date(), time)

    except Exception as e:
        print(f"Error parsing date and time: {e}")
        return None



