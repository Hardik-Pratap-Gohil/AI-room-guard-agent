# tts_demo.py
# Requirements:
#   pip install gTTS pygame
# Run from a regular terminal on Windows.

from gtts import gTTS
import pygame
import tempfile
import time
import os
from enum import Enum

class VoiceMode(Enum):
    NORMAL = "normal"
    FRIENDLY = "friendly"
    ALERT = "alert"

class SimpleTTS:
    """gTTS + pygame player with safe temp-file cleanup (English + Hindi only)."""
    def __init__(self, audio_freq=22050):
        pygame.mixer.init(frequency=audio_freq)
        self._music = pygame.mixer.music

    def _save_tts_to_file(self, text, lang='en', slow=False):
        tts = gTTS(text=text, lang=lang, slow=slow)
        fd, path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)                 # close OS handle so gTTS can write on Windows
        tts.save(path)
        return path

    def _play_and_cleanup(self, path, wait=True, remove_retries=6, retry_delay=0.15):
        try:
            self._music.load(path)
            self._music.play()
            if wait:
                # block until playback completes
                while self._music.get_busy():
                    time.sleep(0.05)
            # stop & attempt to unload (unload may not exist in old pygame; guard it)
            try:
                self._music.stop()
            except Exception:
                pass
            unload = getattr(self._music, "unload", None)
            if callable(unload):
                try:
                    unload()
                except Exception:
                    pass
        finally:
            # Try removing the file; on Windows, the audio driver may still hold file for tiny moment
            for i in range(remove_retries):
                try:
                    os.unlink(path)
                    break
                except PermissionError:
                    time.sleep(retry_delay)
                except FileNotFoundError:
                    break
                except Exception:
                    # give up after retries
                    try:
                        os.unlink(path)
                        break
                    except Exception:
                        break

    def speak(self, text, lang='en', mode=VoiceMode.NORMAL):
        """
        Speak text.
         - lang: 'en' or 'hi'
         - mode affects 'slow' flag and is only a simple heuristic (gTTS only supports slow=True/False)
        """
        slow = False
        if mode == VoiceMode.ALERT:
            # slower speech for clarity on alerts
            slow = True
        elif mode == VoiceMode.FRIENDLY:
            slow = False  # friendly = normal speed, more upbeat (gTTS doesn't support pitch)
        # produce and play
        try:
            path = self._save_tts_to_file(text, lang=lang, slow=slow)
            self._play_and_cleanup(path, wait=True)
        except Exception as e:
            print("TTS error:", e)

    def quit(self):
        try:
            pygame.mixer.quit()
        except Exception:
            pass

# ---------------- Demo ----------------
def demo():
    tts = SimpleTTS()
    print("=== Short demo: English  ===\n")

    # English (US-ish) normal
    print("1) English (normal)")
    tts.speak("Guard mode activated. I am now monitoring this room.", lang='en', mode=VoiceMode.NORMAL)

    # Friendly (English)
    print("2) English (friendly)")
    tts.speak("Hello! I recognize you. Welcome back!", lang='en', mode=VoiceMode.FRIENDLY)

    # Alert (English)
    print("3) English (alert)")
    tts.speak("Excuse me, I don't recognize you. Please identify yourself.", lang='en', mode=VoiceMode.ALERT)

    # Hindi (normal)
    print("4) Hindi (normal)")
    tts.speak("सावधान! यह कमरा निगरानी में है। कृपया अपनी पहचान बताएं।", lang='hi', mode=VoiceMode.NORMAL)

    print("\nDemo complete.")
    tts.quit()

if __name__ == "__main__":
    demo()