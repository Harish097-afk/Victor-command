#advance voice command assistant
# Remove print statements and organize imports
import speech_recognition as sr
import pyttsx3
import datetime
import webbrowser
import os
import logging
from dotenv import load_dotenv
import subprocess
import json
import re
import random
import requests
import pyautogui
import ctypes
from bs4 import BeautifulSoup
import threading
import time
import wikipedia
from typing import Dict, List, Callable, Optional
from datetime import datetime
import psutil  # Add this import at the top if not already present

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('victor.log'),
        logging.StreamHandler()
    ]
)

# Create logger for this module
logger = logging.getLogger(__name__)

class Config:
    def __init__(self, config_file='config.json'):
        self.settings = self.load_config(config_file)
    
    def load_config(self, file_path):
        """Load and validate configuration from JSON file"""
        try:
            with open(file_path, 'r') as f:
                settings = json.load(f)
            return settings
        except FileNotFoundError:
            # Create default config if file doesn't exist
            default_config = {
                "voice": {
                    "rate": 150,
                    "volume": 1.0,
                    "voice_id": None
                },
                "microphone": {
                    "timeout": 5,
                    "phrase_time_limit": 10,
                    "energy_threshold": 4000
                },
                "api_keys": {
                    "weather": os.getenv('OPENWEATHER_API_KEY')
                }
            }
            # Save default config
            with open(file_path, 'w') as f:
                json.dump(default_config, f, indent=4)
            return default_config
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in config file: {file_path}")
            return {}

class PluginManager:
    def __init__(self):
        self.plugins = {}
    
    def register_plugin(self, name, plugin_class):
        self.plugins[name] = plugin_class()
    
    def execute_plugin(self, name, command):
        return self.plugins[name].execute(command)

# Load environment variables
load_dotenv()
API_KEY = os.getenv('OPENWEATHER_API_KEY')

class VictorAssistant:
    def __init__(self, name: str = "Victor", debug: bool = True):
        self.debug = debug
        self.name = name
        logger.info(f"Initializing {self.name} Assistant")
        
        # Load configuration
        self.config = Config()
        
        # Initialize plugin manager
        self.plugin_manager = PluginManager()
        
        # Load environment variables and settings
        load_dotenv()
        self.weather_api_key = self.config.settings.get('api_keys', {}).get('weather') or os.getenv('OPENWEATHER_API_KEY')
        if not self.weather_api_key:
            logger.warning("Weather API key not found")

        # Initialize speech components with config
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.tts_engine = pyttsx3.init()
        
        # Apply configured settings
        voice_settings = self.config.settings.get('voice', {})
        self.tts_engine.setProperty('rate', voice_settings.get('rate', 150))
        self.tts_engine.setProperty('volume', voice_settings.get('volume', 1.0))
        
        mic_settings = self.config.settings.get('microphone', {})
        self.recognizer.pause_threshold = 0.8
        self.recognizer.energy_threshold = mic_settings.get('energy_threshold', 4000)
    
        # Initialize conversation tracking
        self.conversation_history = []
        self.last_command = None
        self.user_name = None
        self.is_listening = False
    
        # Enhanced personality responses with more natural variations
        self.personality_responses = {
            'greeting': [
                "Hey there! Nice to hear from you!",
                "Hi! How's your day going?",
                "Hey! Good to hear your voice!",
                "Hello! Hope you're doing well today!"
            ],
            'how_are_you': [
                "I'm doing pretty good, thanks for asking! How about you?",
                "Can't complain! Though I do wish it was Friday, haha. How are you?",
                "All good here! Just hanging out and ready to help!",
                "Pretty great actually! Always nice to chat with you!"
            ],
            'thanks': [
                "No worries at all! Happy to help!",
                "Anytime! That's what friends are for!",
                "You got it! Let me know if you need anything else!",
                "My pleasure! Always good to chat with you!"
            ],
            'goodbye': [
                "Take care! Don't be a stranger!",
                "Catch you later! Have a great rest of your day!",
                "Bye for now! Looking forward to our next chat!",
                "See you soon! Stay awesome!"
            ],
            'casual': [
                "Oh yeah, I get what you mean!",
                "That's interesting! Tell me more!",
                "Hmm, never thought about it that way!",
                "You know, that's actually pretty cool!"
            ]
        }
        
        # Initialize command registry first
        self.commands: Dict[str, Callable] = {
            'time': self.get_time,
            'date': self.get_date,
            'weather': self.get_weather,
            'search': self.web_search,
            'wikipedia': self.search_wikipedia,
            'wiki': self.search_wikipedia,
            'open': self.open_application,
            'play': self.play_music,
            'volume': self.control_volume,
            'system': self.system_info,
            'shutdown': self.shutdown_system,
            'sleep': self.sleep_system,
            'note': self.take_note,
            'reminder': self.set_reminder,
            'calculate': self.calculator,
            'news': self.get_news,
            'joke': self.tell_joke,
            'repeat': self.repeat_last_command,
            'again': self.repeat_last_command,
            'name': self.handle_name,  # FIXED: changed from 'my name'
            'stop': self.stop_listening,
            'exit': self.stop_listening,
            'quit': self.stop_listening,
            'bye': self.handle_goodbye,
            'history': self.show_command_history,
            'close': self.close_application,
        }
        
        # Update in __init__ method
        self.commands.update({
            'time': self.get_time,
            'what time': self.get_time,
            'current time': self.get_time,
            'date': self.get_date,
            'what date': self.get_date,
            'today': self.get_date,
            'weather': self.get_weather,
            'temperature': self.get_weather,
            'shutdown': self.shutdown_system,
            'sleep': self.sleep_system,
            'scroll': self.browser_navigate,
            'click': self.browser_navigate
        })
        
        # Add thread management
        self.active_threads: List[threading.Thread] = []
        
        # Initialize components
        self.setup_male_voice()
        self.calibrate_microphone()
    
    def setup_male_voice(self):
        """Configure text-to-speech for a deeper male voice"""
        try:
            voices = self.tts_engine.getProperty('voices')
            
            # Try to find a male voice
            male_voice_found = False
            for voice in voices:
                voice_info = voice.name.lower()
                
                if any(keyword in voice_info for keyword in ['david', 'male', 'mark', 'james']):
                    self.tts_engine.setProperty('voice', voice.id)
                    male_voice_found = True
                    break
            
            # Voice properties
            self.tts_engine.setProperty('rate', 150)     # Speech rate
            self.tts_engine.setProperty('volume', 1.0)   # Full volume
            
        except Exception as e:
            logger.error(f"Error setting up voice: {str(e)}")
    
    def calibrate_microphone(self):
        """Calibrate microphone for ambient noise"""
        logger.info("Calibrating microphone for ambient noise...")
        try:
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=2)
            logger.info("Microphone calibration completed")
        except Exception as e:
            logger.error(f"Microphone calibration error: {str(e)}")
    
    def speak(self, text: str):
        """Convert text to speech"""
        try:
            logger.info(f"Speaking: {text}")
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()
        except Exception as e:
            logger.error(f"Speech Error: {str(e)}")
            try:
                self.tts_engine = pyttsx3.init()
                self.setup_male_voice()
                self.tts_engine.say(text)
                self.tts_engine.runAndWait()
            except Exception as e2:
                logger.critical(f"Fatal speech error: {str(e2)}")
    
    def listen(self, timeout: int = 5) -> Optional[str]:
        """Listen for audio input and convert to text"""
        try:
            with self.microphone as source:
                if self.debug:
                    logger.info(f"\nListening... (timeout: {timeout}s)")
                    logger.info("Speak now...")
                
                # Adjust for ambient noise before each listen
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                
                # Get audio input
                try:
                    audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=10)
                    if self.debug:
                        logger.info("Processing speech...")
                except sr.WaitTimeoutError:
                    if self.debug:
                        logger.info("No speech detected within timeout")
                    return None
                
                try:
                    # Try using Google's speech recognition
                    text = self.recognizer.recognize_google(audio).lower()
                    if self.debug:
                        logger.info(f"Recognized: '{text}'")
                    return text
                except sr.UnknownValueError:
                    if self.debug:
                        logger.info("Could not understand audio")
                    return None
                except sr.RequestError as e:
                    if self.debug:
                        logger.info(f"Could not request results; {e}")
                    return None
                    
        except Exception as e:
            if self.debug:
                logger.error(f"Listening error: {str(e)}")
            return None
    
    def handle_personality_response(self, command: str) -> bool:
        """Handle personality-based responses"""
        command_lower = command.lower()
        
        # Greeting responses
        if any(phrase in command_lower for phrase in ['hello', 'hi', 'hey', 'good morning', 'good evening']):
            import random
            response = random.choice(self.personality_responses['greeting'])
            self.speak(response)
            return True
        
        # How are you responses
        if any(phrase in command_lower for phrase in ['how are you', 'how do you feel', 'how is it going']):
            import random
            response = random.choice(self.personality_responses['how_are_you'])
            self.speak(response)
            return True
        
        # Thank you responses
        if any(phrase in command_lower for phrase in ['thank you', 'thanks', 'appreciate']):
            import random
            response = random.choice(self.personality_responses['thanks'])
            self.speak(response)
            return True
        
        # Personal questions
        if 'what is your name' in command_lower or 'who are you' in command_lower:
            self.speak(f"I'm Victor, your personal voice assistant. I'm here to help you with various tasks!")
            return True
        
        if 'tell me about yourself' in command_lower:
            self.speak("I'm Victor, an AI assistant created to help you with daily tasks. I can search Wikipedia, control your system, and have conversations with you!")
            return True
        
        return False
    
    def process_command(self, command: str):
        """Process and execute voice commands"""
        try:
            command = command.lower().strip()
            
            # Handle casual conversation first
            if self.handle_casual_conversation(command):
                return
                
            # Then check for personality responses
            if self.handle_personality_response(command):
                return

            # Check for close command
            if command.startswith("close "):
                self.close_application(command)
                return

            # Check if it's a command
            command_found = False
            for keyword, function in self.commands.items():
                if keyword in command:
                    function(command)
                    command_found = True
                    break

            # If no command found, try Wikipedia as fallback
            if not command_found:
                self.search_wikipedia(command)
            
        except Exception as e:
            logger.error(f"Command processing error: {str(e)}")
            self.speak("Oops, something went wrong there. Mind trying that again?")
    
    def handle_name(self, command: str):
        """Handle name-related queries"""
        try:
            if any(phrase in command for phrase in ['what is my name', 'do you know my name']):
                if self.user_name and self.user_name != "friend":
                    self.speak(f"Your name is {self.user_name}!")
                else:
                    self.speak("I don't know your name yet. What should I call you?")
            elif any(phrase in command for phrase in ['my name is', 'call me', 'i am']):
                # Extract name from command
                for phrase in ['my name is', 'call me', 'i am']:
                    if phrase in command:
                        new_name = command.split(phrase)[-1].strip().title()
                        if new_name:
                            self.user_name = new_name
                            self.speak(f"Got it! I'll call you {new_name} from now on.")
                            return
                self.speak("I didn't catch your name. Could you repeat it?")
        except Exception as e:
            logger.error(f"Name handling error: {str(e)}")
            self.speak("I had trouble processing your name request")
    
    def get_time(self, command: str):
        """Get current time"""
        try:
            current_time = datetime.now().strftime("%I:%M %p")
            day_part = "morning" if 5 <= datetime.now().hour < 12 else \
                       "afternoon" if 12 <= datetime.now().hour < 17 else \
                       "evening" if 17 <= datetime.now().hour < 21 else "night"
            
            self.speak(f"The current time is {current_time}, good {day_part}!")
        except Exception as e:
            logger.error(f"Time error: {str(e)}")
            self.speak("Sorry, I couldn't get the current time")
    
    def get_date(self, command: str):
        """Get current date"""
        try:
            current_date = datetime.now()
            date_str = current_date.strftime("%A, %B %d, %Y")
            
            # Add suffix to day number (1st, 2nd, 3rd, etc.)
            day = current_date.day
            if 4 <= day <= 20 or 24 <= day <= 30:
                suffix = "th"
            else:
                suffix = ["st", "nd", "rd"][day % 10 - 1] if day % 10 <= 3 else "th"
                
            date_str = date_str.replace(str(day), f"{day}{suffix}")
            self.speak(f"Today is {date_str}")
        except Exception as e:
            logger.error(f"Date error: {str(e)}")
            self.speak("Sorry, I couldn't get the current date")
    
    def get_weather(self, command: str):
        """Get live weather information"""
        try:
            if not self.weather_api_key:
                self.speak("Weather service is not configured properly")
                return
                
            # Extract city name from command
            city = command.replace('weather', '').replace('in', '').replace('at', '').strip()
            
            # If no city in command, ask for it
            if not city:
                self.speak("Which city's weather would you like to know?")
                city_response = self.listen(timeout=5)
                if city_response:
                    city = city_response.strip()
                else:
                    self.speak("Sorry, I didn't catch the city name.")
                    return

            # Print debug info
            if self.debug:
                logger.info(f"Fetching weather for city: {city}")
                logger.info(f"Using API endpoint: http://api.openweathermap.org/data/2.5/weather?q={city}")
            
            # Make API request with error handling
            try:
                url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={self.weather_api_key}&units=metric"
                response = requests.get(url, timeout=10)
                
                # Debug response
                if self.debug:
                    logger.info(f"API Response Status: {response.status_code}")
                    logger.info(f"API Response: {response.text[:200]}...")  # Print first 200 chars
                
                if response.status_code == 200:
                    data = response.json()
                    temp = round(data['main']['temp'])
                    desc = data['weather'][0]['description']
                    humidity = data['main']['humidity']
                    feels_like = round(data['main']['feels_like'])
                    
                    weather_info = (
                        f"The current weather in {city} is {desc} with a temperature of {temp}°C, "
                        f"feels like {feels_like}°C, and humidity of {humidity}%"
                    )
                    self.speak(weather_info)
                elif response.status_code == 404:
                    self.speak(f"Sorry, I couldn't find weather information for {city}. Please check the city name.")
                elif response.status_code == 401:
                    self.speak("Sorry, there seems to be an issue with the weather service authentication.")
                    if self.debug:
                        logger.info("API Key might be invalid or expired")
                else:
                    self.speak(f"Sorry, I couldn't get weather information. Status code: {response.status_code}")
                    
            except requests.Timeout:
                self.speak("The weather service is taking too long to respond. Please try again.")
            except requests.RequestException as e:
                self.speak("Sorry, I'm having trouble connecting to the weather service")
                if self.debug:
                    logger.error(f"Request error: {str(e)}")
                
        except Exception as e:
            logger.error(f"Weather error: {str(e)}")
            self.speak("Sorry, I couldn't get the weather information")
    
    def web_search(self, command: str):
        """Search the web using default browser"""
        try:
            query = command.replace('search', '').replace('for', '').strip()
            if query:
                search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
                webbrowser.open(search_url)
                self.speak(f"I've opened a search for {query}")
            else:
                self.speak("What would you like me to search for?")
        except Exception as e:
            self.speak("I couldn't open the web browser")
            logger.error(f"Web search error: {str(e)}")
    
    def search_wikipedia(self, command: str):
        """Search Wikipedia for information"""
        try:
            # Extract search query
            query = command.replace('wikipedia', '').replace('search', '').replace('what is', '').replace('who is', '').strip()
            
            if not query:
                self.speak("What would you like to search for on Wikipedia?")
                return
            
            try:
                self.speak(f"Searching Wikipedia for {query}...")
                summary = wikipedia.summary(query, sentences=2, auto_suggest=True)
                self.speak(f"According to Wikipedia: {summary}")
                
            except wikipedia.DisambiguationError as e:
                options = e.options[:3]
                self.speak(f"There are multiple matches for {query}. The top options are: {', '.join(options)}")
                
            except wikipedia.PageError:
                self.speak(f"Sorry, I couldn't find any Wikipedia article about {query}")
                
        except Exception as e:
            logger.error(f"Wikipedia Error: {str(e)}")
            self.speak("I encountered an error while searching Wikipedia")
    
    def open_application(self, command: str):
        """Open system applications and browsers"""
        try:
            command = command.lower().strip()
            app_name = command.replace('open', '').strip()
            
            # Define application paths
            app_paths = {
                'chrome': {
                    'path': r'C:\Program Files\Google\Chrome\Application\chrome.exe',
                    'type': 'browser'
                },
                'firefox': {
                    'path': r'C:\Program Files\Mozilla Firefox\firefox.exe',
                    'type': 'browser'
                },
                'brave': {
                    'path': r'C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe',
                    'type': 'browser'
                },
                'calculator': {
                    'path': 'calc.exe',
                    'type': 'system'
                },
                'camera': {
                    'path': 'microsoft.windows.camera:',
                    'type': 'uwp'
                },
                'notepad': {
                    'path': 'notepad.exe',
                    'type': 'system'
                },
                'whatsapp': {
                    'path': 'https://web.whatsapp.com',
                    'type': 'web'
                }
            }
            
            # Find matching app
            for app, details in app_paths.items():
                if app in app_name:
                    if details['type'] == 'browser':
                        try:
                            subprocess.Popen([details['path']])
                            self.speak(f"Opening {app}")
                        except FileNotFoundError:
                            webbrowser.open('https://www.google.com')
                            self.speak(f"Couldn't find {app}, opening default browser")
                    
                    elif details['type'] == 'system':
                        os.system(f'start {details["path"]}')
                        self.speak(f"Opening {app}")
                    
                    elif details['type'] == 'uwp':
                        os.system(f'start {details["path"]}')
                        self.speak(f"Opening {app}")
                    
                    elif details['type'] == 'web':
                        webbrowser.open(details['path'])
                        self.speak(f"Opening {app}")
                    
                    return
            
            self.speak(f"Sorry, I don't know how to open {app_name}")
            
        except Exception as e:
            logger.error(f"Error opening application: {str(e)}")
            self.speak("Sorry, I couldn't open that application")
    
    def close_application(self, command: str):
        """Close system applications based on voice command"""
        try:
            app_name = command.replace('close', '').strip().lower()
            # Map spoken app names to process names (add more as needed)
            app_processes = {
                'chrome': ['chrome.exe'],
                'firefox': ['firefox.exe'],
                'brave': ['brave.exe'],
                'notepad': ['notepad.exe'],
                'calculator': ['Calculator.exe', 'ApplicationFrameHost.exe'],
                'camera': ['WindowsCamera.exe', 'ApplicationFrameHost.exe'],
                'whatsapp': ['chrome.exe'],  # WhatsApp Web runs in browser
            }
            found = False
            for app, proc_list in app_processes.items():
                if app in app_name:
                    closed = False
                    for proc in proc_list:
                        for p in psutil.process_iter(['name']):
                            if p.info['name'] and p.info['name'].lower() == proc.lower():
                                try:
                                    p.terminate()
                                    closed = True
                                except Exception as e:
                                    logger.error(f"Error terminating {proc}: {str(e)}")
                    if closed:
                        self.speak(f"Closed {app}")
                    else:
                        self.speak(f"{app} is not running")
                    found = True
                    break
            if not found:
                self.speak(f"Sorry, I don't know how to close {app_name}")
        except Exception as e:
            logger.error(f"Error closing application: {str(e)}")
            self.speak("Sorry, I couldn't close that application")
    
    def system_info(self, command: str):
        """Get basic system information"""
        try:
            import platform
            system = platform.system()
            self.speak(f"You're running {system}")
        except Exception as e:
            self.speak("I couldn't retrieve system information")
            logger.error(f"System info error: {str(e)}")
    
    # Placeholder methods for missing functions
    def play_music(self, command: str):
        self.speak("Music playback feature is not implemented yet")
    
    def control_volume(self, command: str):
        self.speak("Volume control feature is not implemented yet")
    
    def sleep_system(self, command: str):
        """Put system to sleep"""
        try:
            self.speak("Putting the system to sleep")
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
        except Exception as e:
            logger.error(f"Sleep error: {str(e)}")
    
    def set_reminder(self, command: str):
        self.speak("Reminder feature is not implemented yet")
    
    def calculator(self, command: str):
        self.speak("Calculator feature is not implemented yet")
    
    def get_news(self, command: str):
        self.speak("News feature is not implemented yet")
    
    def tell_joke(self, command: str):
        jokes = [
            "Why don't scientists trust atoms? Because they make up everything!",
            "Why did the math book look so sad? Because it was full of problems!",
            "What do you call a fake noodle? An impasta!"
        ]
        import random
        self.speak(random.choice(jokes))
    
    def repeat_last_command(self, command: str):
        if self.last_command:
            self.speak(f"Your last command was: {self.last_command}")
        else:
            self.speak("You haven't given me any commands yet")
    
    def stop_listening(self, command: str):
        """Stop the assistant from listening"""
        try:
            self.speak("Stopping assistant. Goodbye!")
            self.is_listening = False  # This will break the listening loop
            # Cancel any pending operations
            if hasattr(self, 'active_threads'):
                for thread in self.active_threads:
                    if thread.is_alive():
                        thread.join(timeout=1)
        except Exception as e:
            logger.error(f"Error stopping assistant: {str(e)}")
            self.is_listening = False  # Force stop even if there's an error
    
    def handle_goodbye(self, command: str):
        import random
        response = random.choice(self.personality_responses['goodbye'])
        self.speak(response)
        self.is_listening = False
    
    def show_command_history(self, command: str):
        if self.conversation_history:
            self.speak(f"You've given me {len(self.conversation_history)} commands today")
        else:
            self.speak("No command history yet")
    
    def take_note(self, command: str):
        self.speak("Note taking feature is not implemented yet")
    
    def shutdown_system(self, command: str):
        """Shutdown the system"""
        try:
            if "confirm" in command.lower():
                self.speak("Shutting down the system in 30 seconds")
                os.system("shutdown /s /t 30")
            else:
                self.speak("Please say 'shutdown confirm' to confirm system shutdown")
        except Exception as e:
            logger.error(f"Shutdown error: {str(e)}")

    def ask_user_name(self):
        """Ask for user's name for personalization"""
        self.speak("By the way, what should I call you?")
        name_response = self.listen(timeout=10)
        if name_response:
            if 'my name is' in name_response:
                self.user_name = name_response.split('my name is')[-1].strip()
            elif 'call me' in name_response:
                self.user_name = name_response.split('call me')[-1].strip()
            elif 'i am' in name_response:
                self.user_name = name_response.split('i am')[-1].strip()
            else:
                self.user_name = name_response.strip()
            
            self.user_name = self.user_name.title()
            self.speak(f"Nice to meet you, {self.user_name}! I'll remember that.")
        else:
            self.speak("No problem, I'll just call you friend!")
            self.user_name = "friend"
    
    def start_listening(self):
        """Start the main listening loop"""
        try:
            self.is_listening = True
            self.speak("Hello! I am Victor, your personal assistant. How can I help you today?")
            
            while self.is_listening:
                logger.info("\n" + "="*50)
                logger.info("Ready for commands! (Say 'stop' or 'exit' to quit)")
                logger.info("Suggested commands: 'what time is it', 'open chrome', 'weather'")
                logger.info("="*50 + "\n")
                
                command = self.listen(timeout=7)  # Increased timeout
                
                if command:
                    logger.info(f"Command received: '{command}'")
                    self.process_command(command)
                    # Add small pause after processing
                    time.sleep(0.5)
                else:
                    # Only speak if no command was recognized
                    if self.debug:
                        logger.info("No command detected, listening again...")
                
                # Add small delay to prevent CPU overuse
                time.sleep(0.1)
            
        except KeyboardInterrupt:
            logger.info("\nStopping assistant...")
        except Exception as e:
            logger.error(f"Error in listening loop: {str(e)}")
        finally:
            self.is_listening = False
            self.speak("Goodbye!")

    def browser_navigate(self, command: str):
        """Navigate browser based on voice commands"""
        try:
            command = command.lower()
            
            # Extract URL or search query
            if "go to" in command:
                url = command.split("go to")[-1].strip()
                if not url.startswith(('http://', 'https://')):
                    url = 'https://' + url
                webbrowser.open(url)
                self.speak(f"Navigating to {url}")
                
            elif "search for" in command:
                query = command.split("search for")[-1].strip()
                search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
                webbrowser.open(search_url)
                self.speak(f"Searching for {query}")
                
            elif "scroll" in command:
                if "down" in command:
                    pyautogui.scroll(-300)
                elif "up" in command:
                    pyautogui.scroll(300)
                    
            elif "click" in command:
                pyautogui.click()
                
        except Exception as e:
            logger.error(f"Browser navigation error: {str(e)}")
            self.speak("Sorry, I couldn't perform that browser action")

    def handle_casual_conversation(self, command: str) -> bool:
        """Handle casual conversations and small talk"""
        command_lower = command.lower()
        
        # Feeling responses
        if any(phrase in command_lower for phrase in ['feeling down', 'feeling sad', 'had a bad day']):
            responses = [
                "Hey, sorry to hear that. Want to talk about it?",
                "That's rough. Remember tomorrow's a new day though!",
                "We all have those days. What happened?"
            ]
            self.speak(random.choice(responses))
            return True
        
        # Opinion questions
        if any(phrase in command_lower for phrase in ['what do you think', 'your opinion']):
            self.speak("Well, that's an interesting question! While I try to be helpful, I think it's best if you make your own judgment on that.")
            return True
        
        # Casual questions about Victor
        if any(phrase in command_lower for phrase in ['you like', 'your favorite']):
            responses = [
                "You know, I'm more interested in helping you out than talking about myself!",
                "That's a fun question! Though I should probably stay focused on helping you.",
                "Hmm, let me think about that while I help you with something!"
            ]
            self.speak(random.choice(responses))
            return True
        
        # Jokes or fun
        if any(phrase in command_lower for phrase in ['boring', 'funny', 'joke', 'laugh']):
            responses = [
                "Well, I could tell you a joke about programming, but I'm afraid it might be too binary!",
                "Hey, at least I'm trying to keep things interesting! Unlike some other AIs I know...",
                "Would a dad joke help? Because I've got plenty of those!"
            ]
            self.speak(random.choice(responses))
            return True
            
        return False


# FIXED: Proper main execution
def main():
    """Main function to run the assistant"""
    logger.info("Starting Victor Assistant...")
    logger.info("Make sure your microphone is working and connected.")
    logger.info("Press Ctrl+C to stop the assistant at any time.")
    
    try:
        assistant = VictorAssistant(debug=True)
        assistant.start_listening()
    except KeyboardInterrupt:
        logger.info("\nShutting down Victor Assistant...")
    except Exception as e:
        logger.error(f"Error starting assistant: {str(e)}")
        logger.info("Please check that you have the required packages installed:")
        logger.info("pip install speech-recognition pyttsx3 wikipedia-api requests")


class WeatherPlugin:
    def execute(self, command: str):
        # Example weather plugin implementation
        return f"Weather plugin processing: {command}"

# Add this after creating the assistant instance in main()
def setup_plugins(assistant):
    """Register available plugins"""
    assistant.plugin_manager.register_plugin("weather", WeatherPlugin)

if __name__ == "__main__":
    assistant = VictorAssistant(debug=True)
    setup_plugins(assistant)  # Register plugins
    try:
        assistant.start_listening()
    except KeyboardInterrupt:
        logger.info("\nShutting down...")