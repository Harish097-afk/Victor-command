import unittest
from unittest.mock import MagicMock, patch
import sys

# Mock modules that fail to import or initialize without hardware/GUI
sys.modules['pyautogui'] = MagicMock()
sys.modules['speech_recognition'] = MagicMock()
sys.modules['pyttsx3'] = MagicMock()
sys.modules['psutil'] = MagicMock()

from main import VictorAssistant

class TestVictorAssistant(unittest.TestCase):
    def setUp(self):
        self.assistant = VictorAssistant(debug=False)
        self.assistant.speak = MagicMock()

    def test_get_time(self):
        with patch('main.datetime') as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = "10:00 AM"
            mock_datetime.now.return_value.hour = 10
            self.assistant.get_time("what time is it")
            self.assistant.speak.assert_called_with("The current time is 10:00 AM, good morning!")

    def test_handle_name_set(self):
        self.assistant.handle_name("my name is jules")
        self.assertEqual(self.assistant.user_name, "Jules")
        self.assistant.speak.assert_called_with("Got it! I'll call you Jules from now on.")

    def test_handle_name_query_unknown(self):
        self.assistant.user_name = None
        self.assistant.handle_name("what is my name")
        self.assistant.speak.assert_called_with("I don't know your name yet. What should I call you?")

    def test_handle_name_query_known(self):
        self.assistant.user_name = "Jules"
        self.assistant.handle_name("what is my name")
        self.assistant.speak.assert_called_with("Your name is Jules!")

    def test_weather_extraction(self):
        self.assistant.weather_api_key = "fake_key"
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {
                'main': {'temp': 20, 'humidity': 50, 'feels_like': 19},
                'weather': [{'description': 'clear sky'}]
            }
            self.assistant.get_weather("what is the weather in London")
            mock_get.assert_called()
            args, _ = mock_get.call_args
            self.assertIn("q=London", args[0])

    def test_wikipedia_extraction(self):
        with patch('wikipedia.summary') as mock_summary:
            mock_summary.return_value = "Python is a programming language."
            self.assistant.search_wikipedia("tell me about python")
            mock_summary.assert_called_with("python", sentences=2, auto_suggest=True)

if __name__ == '__main__':
    unittest.main()
