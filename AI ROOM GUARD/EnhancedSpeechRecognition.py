"""
EnhancedSpeechRecognition.py - FIXED STATE MANAGEMENT

Fixed issues:
1. Command processing now works correctly even after failed guard mode activation
2. Enrollment command is always checked first before guard mode checks
3. NEW FIX: State only changes if the command callback confirms success
"""

import os
os.environ["PATH"] += os.pathsep + "/opt/homebrew/bin"

import speech_recognition as sr
import threading
import time
from enum import Enum
from difflib import SequenceMatcher

class SystemState(Enum):
    IDLE = "idle"
    GUARD_MODE = "guard_mode"
    ENROLL_MODE = "enroll_mode"
    TRUSTED_CONVERSATION = "trusted_conversation"

class EnhancedSpeechRecognizer:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.microphone = None
        self.state = SystemState.IDLE
        self.listening = False
        self.stop_listening = None
        self.phrase_time_limit = 5
        self.needs_restart = False
        
        # Callbacks for different speech types
        self.on_command = None
        self.on_enrollment_name = None
        self.on_intruder_speech = None
        self.on_trusted_speech = None
        
        # Lock to serialize restarts and avoid races
        self.listener_lock = threading.Lock()
        
        # Configure recognizer settings - MORE SENSITIVE
        self.recognizer.energy_threshold = 180
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.dynamic_energy_adjustment_damping = 0.15
        self.recognizer.dynamic_energy_ratio = 1.5
        self.recognizer.pause_threshold = 0.8
        
        # Create initial microphone and adjust
        self._create_microphone_and_adjust()
        
        print("✓ Enhanced speech recognition ready")
        print(f"  Energy threshold: {self.recognizer.energy_threshold}")
        print(f"  Pause threshold: {self.recognizer.pause_threshold}s")
    
    def _create_microphone_and_adjust(self):
        """Create a new Microphone instance and adjust for ambient noise"""
        try:
            self.microphone = sr.Microphone()
            print("🎤 Adjusting for ambient noise (please be quiet)...", end=" ")
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=2.0)
            print("✓ Done")
            print(f"   Adjusted energy threshold: {self.recognizer.energy_threshold}")
        except Exception as e:
            print(f"Warning: failed to create/adjust Microphone: {e}")
            self.microphone = None
    
    def fuzzy_match(self, text, target_words, threshold=0.7):
        """Enhanced fuzzy matching with better tolerance"""
        word_variants = {
            'guard': ['card', 'god', 'gard', 'guards', 'yard', 'hard', 'god', 'gut', 'cart'],
            'mode': ['mod', 'made', 'mood', 'mold', 'node', 'most'],
            'on': ['an', 'own', 'one', 'in', 'and'],
            'off': ['of', 'rough', 'cough', 'ough'],
            'enroll': ['in roll', 'and roll', 'enrol', 'unroll', 'roll', 'in role']
        }
        
        words = text.lower().split()
        matched_words = []
        
        for target in target_words:
            best_match = None
            best_score = 0
            
            # Check exact match first
            if target in words:
                matched_words.append(target)
                continue
            
            # Check known variants
            if target in word_variants:
                for variant in word_variants[target]:
                    if variant in words or variant in text.lower():
                        matched_words.append(target)
                        best_match = target
                        break
                if best_match:
                    continue
            
            # Fuzzy matching
            for word in words:
                similarity = SequenceMatcher(None, target, word).ratio()
                if similarity > threshold and similarity > best_score:
                    best_score = similarity
                    best_match = target
            
            if best_match and best_score > threshold:
                matched_words.append(target)
        
        return matched_words
    
    def configure_for_mode(self):
        """Adjust speech recognition parameters based on current mode"""
        if self.state == SystemState.GUARD_MODE:
            self.recognizer.pause_threshold = 1.5
            self.recognizer.energy_threshold = 180
            self.phrase_time_limit = None
            print(f"📊 Speech adjusted for GUARD MODE")
            print(f"   Pause: {self.recognizer.pause_threshold}s | Energy: {self.recognizer.energy_threshold}")
        
        elif self.state == SystemState.ENROLL_MODE:
            self.recognizer.pause_threshold = 1.0
            self.recognizer.energy_threshold = 180
            self.phrase_time_limit = 5
            print(f"📊 Speech adjusted for ENROLLMENT MODE")
            print(f"   Pause: {self.recognizer.pause_threshold}s | Energy: {self.recognizer.energy_threshold}")
        
        elif self.state == SystemState.TRUSTED_CONVERSATION:
            self.recognizer.pause_threshold = 2.0
            self.recognizer.energy_threshold = 180
            self.phrase_time_limit = 20
            
            self.recognizer.dynamic_energy_threshold = True
            self.recognizer.dynamic_energy_adjustment_damping = 0.15
            self.recognizer.dynamic_energy_ratio = 1.5
            
            print(f"📊 Speech adjusted for CONVERSATION MODE")
            print(f"   Pause threshold: {self.recognizer.pause_threshold}s (wait for silence)")
            print(f"   Energy threshold: {self.recognizer.energy_threshold} (word gap tolerance)")
            print(f"   Max phrase length: {self.phrase_time_limit}s")
            print(f"   [Continuous listening - say 'bye' to end]")
        
        else:
            self.recognizer.pause_threshold = 0.8
            self.recognizer.energy_threshold = 250
            self.phrase_time_limit = 5
            print(f"📊 Speech adjusted for IDLE MODE (commands)")
            print(f"   Pause: {self.recognizer.pause_threshold}s | Energy: {self.recognizer.energy_threshold}")
    
    def restart_listener(self):
        """Restart the background listener with new parameters"""
        with self.listener_lock:
            if self.stop_listening is not None:
                print("⏸️  Stopping current listener...")
                try:
                    self.stop_listening(wait_for_stop=True)
                except Exception as e:
                    print(f"Warning: stop_listening raised exception: {e}")
                time.sleep(0.2)
            
            try:
                self.microphone = sr.Microphone()
                with self.microphone as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.8)
            except Exception as e:
                print(f"Failed to create microphone: {e}")
                self.microphone = None
                return
            
            print("▶️  Starting listener with new parameters...")
            try:
                self.stop_listening = self.recognizer.listen_in_background(
                    self.microphone,
                    self.speech_callback,
                    phrase_time_limit=self.phrase_time_limit
                )
                self.needs_restart = False
                print("✓ Listener restarted\n")
            except AssertionError as ae:
                print(f"AssertionError: {ae}. Retrying...")
                time.sleep(0.4)
                try:
                    self.microphone = sr.Microphone()
                    with self.microphone as source:
                        self.recognizer.adjust_for_ambient_noise(source, duration=0.6)
                    self.stop_listening = self.recognizer.listen_in_background(
                        self.microphone,
                        self.speech_callback,
                        phrase_time_limit=self.phrase_time_limit
                    )
                    self.needs_restart = False
                    print("✓ Listener restarted on retry\n")
                except Exception as e:
                    print(f"Failed to restart: {e}")
                    self.stop_listening = None
    
    def process_command(self, text):
        """Process recognized text for commands - FIXED ORDER"""
        text_lower = text.lower().strip()
        
        # Command patterns
        guard_on_words = ['guard', 'mode', 'on']
        guard_off_words = ['guard', 'mode', 'off']
        enroll_words = ['enroll', 'enrol']
        
        # CRITICAL FIX: Check enrollment FIRST, regardless of state
        # This ensures "enroll" always works, even after failed guard mode
        matched_enroll = self.fuzzy_match(text_lower, enroll_words, threshold=0.65)
        if matched_enroll:
            # Only activate enrollment if we're in IDLE state
            if self.state == SystemState.IDLE:
                self.state = SystemState.ENROLL_MODE
                self.configure_for_mode()
                self.needs_restart = True
                print(f">>> COMMAND: ENROLLMENT MODE ACTIVATED")
                if self.on_command:
                    self.on_command('enroll', text)
                return True
            else:
                print(f"⚠️  Cannot enroll in {self.state.value} state. Return to idle first.")
                return False
        
        # IMPORTANT: Don't process guard commands during trusted conversation
        # This prevents false positives like "2" being heard as "to/two" triggering "mode off"
        if self.state == SystemState.TRUSTED_CONVERSATION:
            # During trusted conversation, only explicit "guard mode off" with all 3 words should work
            if 'guard' in text_lower and 'mode' in text_lower and 'off' in text_lower:
                # Check that these words appear in order and close together
                words = text_lower.split()
                guard_idx = next((i for i, w in enumerate(words) if 'guard' in w), -1)
                mode_idx = next((i for i, w in enumerate(words) if 'mode' in w or 'mod' in w), -1)
                off_idx = next((i for i, w in enumerate(words) if 'off' in w or w == 'of'), -1)
                
                # All three words must be present and within 4 words of each other
                if guard_idx >= 0 and mode_idx >= 0 and off_idx >= 0:
                    if abs(mode_idx - guard_idx) <= 3 and abs(off_idx - mode_idx) <= 3:
                        # Don't change state here - let callback handle it
                        print(f">>> COMMAND: GUARD MODE OFF (explicit command during conversation)")
                        if self.on_command:
                            result = self.on_command('guard_off', text)
                            # Only change state if command was successful
                            if result is not False:
                                self.state = SystemState.IDLE
                                self.configure_for_mode()
                                self.needs_restart = True
                        return True
            # No command detected during conversation - return False to process as speech
            return False
        
        # Check for guard mode off (should work in any non-conversation state)
        matched_off = self.fuzzy_match(text_lower, guard_off_words, threshold=0.65)
        if len(matched_off) >= 2:
            has_guard_or_mode = 'guard' in matched_off or 'mode' in matched_off
            has_off = 'off' in matched_off
            
            if has_guard_or_mode and has_off and self.state != SystemState.IDLE:
                # Don't change state here - let callback handle it
                print(f">>> COMMAND: GUARD MODE OFF")
                if self.on_command:
                    result = self.on_command('guard_off', text)
                    # Only change state if command was successful
                    if result is not False:
                        self.state = SystemState.IDLE
                        self.configure_for_mode()
                        self.needs_restart = True
                return True
        
        # Check for guard mode on
        matched_on = self.fuzzy_match(text_lower, guard_on_words, threshold=0.65)
        if len(matched_on) >= 2:
            has_guard_or_mode = 'guard' in matched_on or 'mode' in matched_on
            has_on = 'on' in matched_on
            
            if has_guard_or_mode and has_on and self.state != SystemState.GUARD_MODE:
                # CRITICAL FIX: Don't change state yet - let callback decide
                print(f">>> COMMAND: GUARD MODE ON")
                if self.on_command:
                    # Call the callback and check if it succeeded
                    result = self.on_command('guard_on', text)
                    # Only change state if the callback returns True (success)
                    if result is True:
                        self.state = SystemState.GUARD_MODE
                        self.configure_for_mode()
                        self.needs_restart = True
                    # If result is False, stay in current state
                return True
        
        return False
    
    def speech_callback(self, recognizer, audio):
        """Main callback for continuous listening with multiple recognition attempts"""
        try:
            text = None
            
            # DEBUG: Log audio duration
            if self.state == SystemState.TRUSTED_CONVERSATION:
                audio_duration = len(audio.frame_data) / (audio.sample_rate * audio.sample_width)
                print(f"[DEBUG] Audio captured: {audio_duration:.2f}s")
            
            # Primary attempt with alternatives
            try:
                if self.state == SystemState.TRUSTED_CONVERSATION:
                    result = recognizer.recognize_google(audio, language='en-US', show_all=True)
                    
                    if result and 'alternative' in result:
                        alternatives = result['alternative']
                        if alternatives:
                            text = max(alternatives, key=lambda x: len(x.get('transcript', '')))['transcript']
                            print(f"[DEBUG] Got {len(alternatives)} alternatives, chose longest")
                    else:
                        text = recognizer.recognize_google(audio, language='en-US')
                else:
                    text = recognizer.recognize_google(audio, language='en-US')
                    
            except sr.UnknownValueError:
                print(f"[DEBUG] Primary recognition failed, trying fallback...")
                try:
                    result = recognizer.recognize_google(audio, language='en-US', show_all=True)
                    if result and 'alternative' in result:
                        alternatives = result['alternative']
                        if alternatives:
                            text = alternatives[0]['transcript']
                except:
                    pass
            
            if not text:
                return
            
            print(f"🎤 Heard: '{text}' (length: {len(text.split())} words)")
            
            # ALWAYS check for commands first
            command_detected = self.process_command(text)
            
            # If no command detected, route based on state
            if not command_detected:
                if self.state == SystemState.ENROLL_MODE:
                    if self.on_enrollment_name:
                        self.on_enrollment_name(text)
                
                elif self.state == SystemState.TRUSTED_CONVERSATION:
                    if self.on_trusted_speech:
                        self.on_trusted_speech(text)
                
                elif self.state == SystemState.GUARD_MODE:
                    if self.on_intruder_speech:
                        self.on_intruder_speech(text)
                
                print(f"   State: {self.state.value}")
        
        except sr.RequestError as e:
            print(f"❌ Speech recognition service error: {e}")
        except Exception as ex:
            print(f"❌ Unexpected error: {ex}")
            import traceback
            traceback.print_exc()
    
    def start_listening(self):
        """Start continuous speech recognition"""
        self.listening = True
        self.configure_for_mode()
        
        if self.microphone is None:
            self._create_microphone_and_adjust()
        
        print("\n" + "="*60)
        print("🎤 SPEECH RECOGNITION ACTIVE")
        print("="*60)
        print("\nVoice Commands:")
        print("  📢 'Guard Mode On'  - Start monitoring")
        print("  📢 'Guard Mode Off' - Stop monitoring")
        print("  📢 'Enroll'         - Add new trusted face")
        print("\n" + "="*60 + "\n")
        
        try:
            self.stop_listening = self.recognizer.listen_in_background(
                self.microphone,
                self.speech_callback,
                phrase_time_limit=self.phrase_time_limit
            )
        except AssertionError as ae:
            print(f"AssertionError on initial start: {ae}")
            time.sleep(0.3)
            self._create_microphone_and_adjust()
            self.stop_listening = self.recognizer.listen_in_background(
                self.microphone,
                self.speech_callback,
                phrase_time_limit=self.phrase_time_limit
            )
    
    def stop_listening_func(self):
        """Stop continuous speech recognition"""
        with self.listener_lock:
            if self.stop_listening is not None:
                try:
                    self.stop_listening(wait_for_stop=True)
                except Exception as e:
                    print(f"Warning: exception while stopping: {e}")
                finally:
                    self.stop_listening = None
            self.listening = False
            print("🔇 Speech recognition stopped")