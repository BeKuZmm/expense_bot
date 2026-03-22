import speech_recognition as sr
import imageio_ffmpeg
from pydub import AudioSegment
import os
import re

AudioSegment.converter = imageio_ffmpeg.get_ffmpeg_exe()
recognizer = sr.Recognizer()

CATEGORIES = {
    "oziq": "🍔 Oziq-ovqat",
    "ovqat": "🍔 Oziq-ovqat",
    "non": "🍔 Oziq-ovqat",
    "go'sht": "🍔 Oziq-ovqat",
    "transport": "🚗 Transport",
    "taksi": "🚗 Transport",
    "avtobus": "🚗 Transport",
    "kiyim": "👕 Kiyim",
    "dori": "💊 Sog'liq",
    "shifokor": "💊 Sog'liq",
    "kommunal": "🏠 Kommunal",
    "gaz": "🏠 Kommunal",
    "elektr": "🏠 Kommunal",
    "kino": "🎮 Ko'ngilochar",
    "o'yin": "🎮 Ko'ngilochar",
}

def detect_category(text: str) -> str:
    text_lower = text.lower()
    for keyword, category in CATEGORIES.items():
        if keyword in text_lower:
            return category
    return "📦 Boshqa"

def extract_amount(text: str):
    text = text.lower()
    text = text.replace("ming", "000").replace("mln", "000000")
    numbers = re.findall(r'\d+', text.replace(" ", ""))
    if numbers:
        return float(numbers[0])
    return None

def convert_ogg_to_wav(ogg_path: str) -> str:
    wav_path = ogg_path.replace(".ogg", ".wav")
    audio = AudioSegment.from_ogg(ogg_path)
    audio.export(wav_path, format="wav")
    return wav_path

def transcribe_voice(file_path: str) -> str:
    wav_path = convert_ogg_to_wav(file_path)
    with sr.AudioFile(wav_path) as source:
        audio = recognizer.record(source)
    try:
        text = recognizer.recognize_google(audio, language="uz-UZ")
    except sr.UnknownValueError:
        text = ""
    except sr.RequestError:
        text = ""
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)
        if os.path.exists(file_path):
            os.remove(file_path)
    return text
