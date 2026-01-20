# advance voice command assistant
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
import threading
import time
import wikipedia
from typing import Dict, List, Callable, Optional
from datetime import datetime
import psutil

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

        # Enhanced personality responses
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
            ]
        }

        # Initialize command registry
        self.commands: Dict[str, Callable] = {
            'time': self.get_time,
            'date': self.get_date,
            'today': self.get_date,
            'weather': self.get_weather,
            'temperature': self.get_weather,
            'search for': self.browser_navigate,
            'search': self.web_search,
            'wikipedia': self.search_wikipedia,
            'wiki': self.search_wikipedia,
            'what is': self.search_wikipedia,
            'who is': self.search_wikipedia,
            'open': self.open_application,
            'close': self.close_application,
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
            'what is my name': self.handle_name,
            'do you know my name': self.handle_name,
            'my name is': self.handle_name,
            'call me': self.handle_name,
            'i am': self.handle_name,
            'name': self.handle_name,
            'stop': self.stop_listening,
            'exit': self.stop_listening,
            'quit': self.stop_listening,
            'bye': self.handle_goodbye,
            'history': self.show_command_history,
            'go to': self.browser_navigate,
            'scroll': self.browser_navigate,
            'click': self.browser_navigate
        }

        # Add thread management
        self.active_threads: List[threading.Thread] = []

        # Initialize components
        self.setup_male_voice()
        self.calibrate_microphone()

    def setup_male_voice(self):
        """Configure text-to-speech for a deeper male voice"""
        try:
            voices = self.tts_engine.getProperty('voices')
            for voice in voices:
                voice_info = voice.name.lower()
                if any(keyword in voice_info for keyword in ['david', 'male', 'mark', 'james']):
                    self.tts_engine.setProperty('voice', voice.id)
                    break
            self.tts_engine.setProperty('rate', 150)
            self.tts_engine.setProperty('volume', 1.0)
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

                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)

                try:
                    audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=10)
                except sr.WaitTimeoutError:
                    return None

                try:
                    text = self.recognizer.recognize_google(audio).lower()
                    if self.debug:
                        logger.info(f"Recognized: '{text}'")
                    return text
                except sr.UnknownValueError:
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

        if any(phrase in command_lower for phrase in ['hello', 'hi', 'hey', 'good morning', 'good evening']):
            self.speak(random.choice(self.personality_responses['greeting']))
            return True

        if any(phrase in command_lower for phrase in ['how are you', 'how do you feel', 'how is it going']):
            self.speak(random.choice(self.personality_responses['how_are_you']))
            return True

        if any(phrase in command_lower for phrase in ['thank you', 'thanks', 'appreciate']):
            self.speak(random.choice(self.personality_responses['thanks']))
            return True

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
            self.last_command = command
            self.conversation_history.append(command)

            if self.handle_casual_conversation(command):
                return

            if self.handle_personality_response(command):
                return

            if command.startswith("close "):
                self.close_application(command)
                return

            command_found = False
            # Sort keywords by length descending to match longest phrases first
            sorted_keywords = sorted(self.commands.keys(), key=len, reverse=True)
            for keyword in sorted_keywords:
                if keyword in command:
                    self.commands[keyword](command)
                    command_found = True
                    break

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
            now = datetime.now()
            current_time = now.strftime("%I:%M %p")
            day_part = "morning" if 5 <= now.hour < 12 else \
                       "afternoon" if 12 <= now.hour < 17 else \
                       "evening" if 17 <= now.hour < 21 else "night"

            self.speak(f"The current time is {current_time}, good {day_part}!")
        except Exception as e:
            logger.error(f"Time error: {str(e)}")
            self.speak("Sorry, I couldn't get the current time")

    def get_date(self, command: str):
        """Get current date"""
        try:
            current_date = datetime.now()
            date_str = current_date.strftime("%A, %B %d, %Y")
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

            city = command
            # Use regex to replace whole words only
            for word in ['weather', 'temperature', 'in', 'at', 'what', 'is', 'the', 'like', 'current']:
                city = re.sub(r'\b' + word + r'\b', '', city)
            city = " ".join(city.split()) # Clean up multiple spaces

            if not city:
                self.speak("Which city's weather would you like to know?")
                city_response = self.listen(timeout=5)
                if city_response:
                    city = city_response.strip()
                else:
                    self.speak("Sorry, I didn't catch the city name.")
                    return

            try:
                url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={self.weather_api_key}&units=metric"
                response = requests.get(url, timeout=10)

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
                    self.speak(f"Sorry, I couldn't find weather information for {city}.")
                else:
                    self.speak(f"Sorry, I couldn't get weather information.")

            except requests.RequestException:
                self.speak("Sorry, I'm having trouble connecting to the weather service")

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
            query = command
            # Use regex to replace whole words only
            for word in ['wikipedia', 'search', 'what is', 'who is', 'tell me about']:
                query = re.sub(r'\b' + word + r'\b', '', query)
            query = " ".join(query.split()) # Clean up multiple spaces

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
            app_name = command.replace('open', '').strip().lower()
            app_paths = {
                'chrome': {'path': r'C:\Program Files\Google\Chrome\Application\chrome.exe', 'type': 'browser'},
                'firefox': {'path': r'C:\Program Files\Mozilla Firefox\firefox.exe', 'type': 'browser'},
                'calculator': {'path': 'calc.exe', 'type': 'system'},
                'notepad': {'path': 'notepad.exe', 'type': 'system'},
                'whatsapp': {'path': 'https://web.whatsapp.com', 'type': 'web'}
            }

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
                    elif details['type'] == 'web':
                        webbrowser.open(details['path'])
                        self.speak(f"Opening {app}")
                    return
            self.speak(f"Sorry, I don't know how to open {app_name}")
        except Exception as e:
            logger.error(f"Error opening application: {str(e)}")
            self.speak("Sorry, I couldn't open that application")

    def close_application(self, command: str):
        """Close system applications"""
        try:
            app_name = command.replace('close', '').strip().lower()
            app_processes = {
                'chrome': ['chrome.exe'],
                'firefox': ['firefox.exe'],
                'notepad': ['notepad.exe'],
                'calculator': ['Calculator.exe', 'ApplicationFrameHost.exe'],
            }
            for app, proc_list in app_processes.items():
                if app in app_name:
                    closed = False
                    for proc in proc_list:
                        for p in psutil.process_iter(['name']):
                            if p.info['name'] and p.info['name'].lower() == proc.lower():
                                p.terminate()
                                closed = True
                    if closed:
                        self.speak(f"Closed {app}")
                    else:
                        self.speak(f"{app} is not running")
                    return
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
        self.speak(random.choice(jokes))

    def repeat_last_command(self, command: str):
        if self.last_command:
            self.speak(f"Your last command was: {self.last_command}")
        else:
            self.speak("You haven't given me any commands yet")

    def stop_listening(self, command: str):
        """Stop the assistant from listening"""
        self.is_listening = False

    def handle_goodbye(self, command: str):
        self.speak(random.choice(self.personality_responses['goodbye']))
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

    def start_listening(self):
        """Start the main listening loop"""
        try:
            self.is_listening = True
            self.speak("Hello! I am Victor, your personal assistant. How can I help you today?")

            while self.is_listening:
                logger.info("\n" + "="*50)
                logger.info("Ready for commands! (Say 'stop' or 'exit' to quit)")
                logger.info("="*50 + "\n")

                command = self.listen(timeout=7)

                if command:
                    logger.info(f"Command received: '{command}'")
                    self.process_command(command)
                    time.sleep(0.5)

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
        if any(phrase in command_lower for phrase in ['feeling down', 'feeling sad', 'had a bad day']):
            responses = ["Hey, sorry to hear that. Want to talk about it?", "That's rough. Remember tomorrow's a new day though!", "We all have those days. What happened?"]
            self.speak(random.choice(responses))
            return True
        return False

def setup_plugins(assistant):
    """Register available plugins"""
    class WeatherPlugin:
        def execute(self, command: str):
            return f"Weather plugin processing: {command}"
    assistant.plugin_manager.register_plugin("weather", WeatherPlugin)

def main():
    """Main function to run the assistant"""
    logger.info("Starting Victor Assistant...")
    try:
        assistant = VictorAssistant(debug=True)
        setup_plugins(assistant)
        assistant.start_listening()
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
    except Exception as e:
        logger.error(f"Error starting assistant: {str(e)}")
        logger.info("Please check dependencies: pip install SpeechRecognition pyttsx3 wikipedia requests pyautogui psutil python-dotenv")

if __name__ == "__main__":
    main()
