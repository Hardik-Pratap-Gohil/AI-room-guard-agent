"""
main_guard_system.py - ENHANCED WITH BETTER LOGGING

Key improvements:
1. Better event logging format with intruder names
2. Query recent events from last 5 logs instead of just 1
3. Improved intruder handling with name extraction
4. Time-based acceptance ONLY at escalation Level 1
5. Logs intruder names in "Unknown (Name)" format
"""

import os
import sys
import time
import threading
import cv2
import numpy as np
from collections import deque

# Import our modules
from EnhancedSpeechRecognition import EnhancedSpeechRecognizer, SystemState
from TexttoSpeech import SimpleTTS, VoiceMode
from VoiceEnrollment import VoiceEnrollment
from LLMConversationAgent import LLMConversationAgent, EscalationLevel
import face_recognition
import pickle

# Configuration
EMB_FILE = "embeddings.pkl"
SNAP_DIR = "snapshots"
RECOGNITION_THRESHOLD = 0.4
SMOOTH_WINDOW = 5
ACTION_COOLDOWN = 10.0
CONVERSATION_TIMEOUT = 30.0

# PERFORMANCE OPTIMIZATION SETTINGS
FRAME_SKIP = 3
DETECTION_SCALE = 0.25
DISPLAY_SCALE = 0.5


class AIRoomGuard:
    """Main AI Room Guard System with Enhanced Logging and Escalation"""
    
    def __init__(self, llm_provider="gemini", api_key=None):
        """Initialize the guard system"""
        print("\n" + "="*70)
        print("🛡️ AI ROOM GUARD SYSTEM - EE782 Project (Enhanced)")
        print("="*70 + "\n")
        
        # Initialize components
        print("Initializing components...")
        
        # 1. Text-to-Speech (with UK accent)
        self.tts = SimpleTTS(default_accent='co.uk')
        print("✓ TTS initialized (UK accent)")
        
        # 2. Speech Recognition
        self.speech = EnhancedSpeechRecognizer()
        self.speech.on_command = self.handle_voice_command
        self.speech.on_enrollment_name = self.handle_enrollment_name
        self.speech.on_intruder_speech = self.handle_intruder_speech
        self.speech.on_trusted_speech = self.handle_trusted_speech
        print("✓ Speech recognition initialized")
        
        # 3. Voice Enrollment
        self.enrollment = VoiceEnrollment(tts=self.tts)
        print("✓ Voice enrollment initialized")
        
        # 4. LLM Conversation Agent (ENHANCED)
        self.llm_agent = LLMConversationAgent(
            api_key=api_key,
            tts=self.tts
        )
        print("✓ LLM agent initialized (enhanced escalation - Level 1 only acceptance)")
        
        # System state
        self.guard_active = False
        self.enrolling = False
        self.in_conversation = False
        self.in_trusted_conversation = False
        self.current_intruder = None
        self.current_intruder_name = None  # NEW: Track intruder's claimed name
        self.conversation_thread = None
        
        # Face recognition state
        self.face_db = self.load_face_database()
        self.last_action_time = 0
        self.last_detected_person = None
        self.recognition_buffer = deque(maxlen=SMOOTH_WINDOW)
        self.last_speech_time = time.time()
        
        # Video capture
        self.cap = None
        self.video_thread = None
        self.video_running = False
        
        # PERFORMANCE: Frame counter for skipping
        self.frame_counter = 0
        
        # Conversation timeout thread
        self.timeout_thread = None
        self.timeout_active = False
        
        # NEW: Intruder response timeout monitoring
        self.intruder_timeout_thread = None
        self.intruder_timeout_active = False
        
        # Event log for tracking activities
        self.event_log = []
        
        print("\n✅ All components initialized!\n")
    
    def load_face_database(self):
        """Load enrolled faces from disk"""
        if os.path.exists(EMB_FILE):
            with open(EMB_FILE, "rb") as f:
                raw = pickle.load(f)
            db = {name: [np.array(e) for e in arr] for name, arr in raw.items()}
            print(f"📂 Loaded {len(db)} enrolled person(s): {list(db.keys())}")
            return db
        print("📂 No enrolled faces found. Use 'Enroll' to add trusted persons.")
        return {}
    
    def reload_face_database(self):
        """Reload face database (after enrollment)"""
        self.face_db = self.load_face_database()
    
    def start(self):
        """Start the guard system"""
        print("\n" + "="*70)
        print("🎤 VOICE CONTROL ACTIVE - Listening for commands...")
        print("="*70)
        
        # Start speech recognition
        self.speech.start_listening()
        
        try:
            # Main loop
            while True:
                # Check if speech recognizer needs restart
                if self.speech.needs_restart:
                    self.speech.restart_listener()
                
                time.sleep(0.1)
        
        except KeyboardInterrupt:
            print("\n\n🛑 Shutting down...")
            self.shutdown()
    
    def shutdown(self):
        """Shutdown the system gracefully"""
        print("Stopping all components...")
        
        # Stop timeout monitoring
        self.timeout_active = False
        
        # Stop video
        self.stop_video_monitoring()
        
        # Stop speech recognition
        self.speech.stop_listening_func()
        
        # Quit TTS
        self.tts.quit()
        
        print("✅ Shutdown complete")
        sys.exit(0)
    
    # ==================== VOICE COMMAND HANDLERS ====================
    
    def handle_voice_command(self, command, text):
        """Handle voice commands"""
        print(f"\n{'='*70}")
        print(f"🎙️ COMMAND: {command.upper()}")
        print(f"{'='*70}\n")
        
        if command == 'guard_on':
            return self.activate_guard_mode()
        elif command == 'guard_off':
            return self.deactivate_guard_mode()
        elif command == 'enroll':
            return self.start_enrollment()
        
        return False
    
    def activate_guard_mode(self):
        """Activate guard mode"""
        if self.guard_active:
            msg = "Guard mode is already active"
            print(f"ℹ️ {msg}")
            self.tts.speak(msg, mode=VoiceMode.NORMAL)
            return
        
        if not self.face_db:
            msg = "Cannot activate guard mode. No trusted persons enrolled."
            print(f"❌ {msg}")
            self.tts.speak(msg, mode=VoiceMode.ALERT)
            return
        
        self.guard_active = True
        self.log_event(f"Guard mode activated - monitoring for {len(self.face_db)} trusted person(s)", "GUARD_ACTIVATED")
        
        msg = f"Guard mode activated. Monitoring for {len(self.face_db)} trusted person(s)."
        print(f"\n🛡️ {msg}")
        self.tts.speak(msg, mode=VoiceMode.NORMAL)
        
        self.start_video_monitoring()
    
    def deactivate_guard_mode(self):
        """Deactivate guard mode"""
        if not self.guard_active:
            return
        
        self.guard_active = False
        self.in_trusted_conversation = False
        self.timeout_active = False
        
        self.log_event("Guard mode deactivated", "GUARD_DEACTIVATED")
        
        msg = "Guard mode deactivated."
        print(f"\n🔓 {msg}")
        self.tts.speak(msg, mode=VoiceMode.NORMAL)
        
        self.stop_video_monitoring()
    
    def start_enrollment(self):
        """Start enrollment"""
        if self.guard_active:
            msg = "Cannot enroll while guard mode is active."
            print(f"⚠️ {msg}")
            self.tts.speak(msg, mode=VoiceMode.ALERT)
            return
        
        self.enrolling = True
        self.enrollment.start_enrollment()
    
    def handle_enrollment_name(self, name):
        """Handle enrollment"""
        if not self.enrolling or not self.enrollment.is_active():
            return
        
        self.enrollment.set_person_name(name)
        photos = self.enrollment.capture_photos_from_webcam()
        
        if photos:
            success = self.enrollment.process_enrollment(photos)
            if success:
                self.reload_face_database()
                self.log_event(f"New person enrolled: {name}", "ENROLLMENT")
        
        self.enrolling = False
        self.enrollment.reset()
    
    # ==================== VIDEO MONITORING ====================
    
    def start_video_monitoring(self):
        """Start video monitoring"""
        if self.video_running:
            return
        
        self.video_running = True
        self.frame_counter = 0
        self.video_thread = threading.Thread(target=self.video_monitoring_loop, daemon=True)
        self.video_thread.start()
        print("📹 Video monitoring started")
    
    def stop_video_monitoring(self):
        """Stop video monitoring"""
        self.video_running = False
        if self.video_thread:
            self.video_thread.join(timeout=2.0)
        if self.cap:
            self.cap.release()
            self.cap = None
        cv2.destroyAllWindows()
        print("📹 Video monitoring stopped")
    
    def video_monitoring_loop(self):
        """Main video loop"""
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            print("❌ Cannot open webcam")
            self.guard_active = False
            return
        
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        last_faces = []
        
        while self.video_running and self.guard_active:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.01)
                continue
            
            self.frame_counter += 1
            
            if not self.in_trusted_conversation:
                if self.frame_counter % FRAME_SKIP == 0:
                    detected_faces = self.process_frame(frame)
                    if detected_faces:
                        last_faces = detected_faces
            else:
                last_faces = []
            
            display_frame = self.draw_display_frame(frame, last_faces)
            
            if DISPLAY_SCALE != 1.0:
                w = int(frame.shape[1] * DISPLAY_SCALE)
                h = int(frame.shape[0] * DISPLAY_SCALE)
                display_frame = cv2.resize(display_frame, (w, h))
            
            cv2.imshow("AI Room Guard - Press 'q' to exit", display_frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()
    
    def process_frame(self, frame):
        """Process frame for face recognition"""
        small = cv2.resize(frame, (0, 0), fx=DETECTION_SCALE, fy=DETECTION_SCALE)
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        
        face_locations = face_recognition.face_locations(rgb, model='hog')
        
        if not face_locations:
            return []
        
        face_encodings = face_recognition.face_encodings(rgb, face_locations)
        
        detected_faces = []
        
        for (top, right, bottom, left), encoding in zip(face_locations, face_encodings):
            name, distance = self.match_face(encoding)
            
            detected_faces.append({
                'location': (top, right, bottom, left),
                'name': name,
                'distance': distance,
                'encoding': encoding
            })
            
            self.recognition_buffer.append(name)
            
            if len(self.recognition_buffer) >= SMOOTH_WINDOW:
                recognized = self.majority_vote(self.recognition_buffer)
                
                current_time = time.time()
                if current_time - self.last_action_time < ACTION_COOLDOWN:
                    if recognized == self.last_detected_person:
                        continue
                
                if recognized != "Unknown":
                    self.handle_trusted_person(recognized, frame)
                    self.last_detected_person = recognized
                else:
                    self.handle_unknown_person(frame)
                    self.last_detected_person = "Unknown"
                
                self.last_action_time = current_time
        
        return detected_faces
    
    def match_face(self, encoding):
        """Match face encoding"""
        if not self.face_db:
            return "Unknown", 999.0
        
        best_name = None
        best_distance = float('inf')
        
        for name, embeddings in self.face_db.items():
            for emb in embeddings:
                distance = np.linalg.norm(encoding - emb)
                if distance < best_distance:
                    best_distance = distance
                    best_name = name
        
        if best_distance < RECOGNITION_THRESHOLD:
            return best_name, best_distance
        else:
            return "Unknown", best_distance
    
    def majority_vote(self, buffer):
        """Get majority vote"""
        if not buffer:
            return None
        counts = {}
        for name in buffer:
            counts[name] = counts.get(name, 0) + 1
        return max(counts, key=counts.get)
    
    def draw_display_frame(self, frame, faces):
        """Draw on frame"""
        display = frame.copy()
        
        if self.in_trusted_conversation:
            status = "IN CONVERSATION - Monitoring Paused"
            color = (0, 200, 255)
        elif self.guard_active:
            status = "GUARD MODE: ACTIVE"
            color = (0, 255, 0)
        else:
            status = "GUARD MODE: OFF"
            color = (0, 0, 255)
        
        cv2.putText(display, status, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
        
        if not self.in_trusted_conversation:
            for face_info in faces:
                top, right, bottom, left = face_info['location']
                name = face_info['name']
                distance = face_info['distance']
                
                scale = 1.0 / DETECTION_SCALE
                top = int(top * scale)
                right = int(right * scale)
                bottom = int(bottom * scale)
                left = int(left * scale)
                
                color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
                cv2.rectangle(display, (left, top), (right, bottom), color, 2)
                
                label = f"{name} ({distance:.2f})"
                cv2.putText(display, label, (left, top - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
        return display
    
    # ==================== PERSON HANDLERS ====================
    
    def handle_trusted_person(self, name, frame):
        """Handle trusted person"""
        print(f"\n{'='*70}")
        print(f"✅ TRUSTED PERSON: {name}")
        print(f"{'='*70}\n")
        
        self.log_event(f"Trusted person detected: {name}", "TRUSTED_ENTRY")
        self.save_snapshot(frame, name)
        
        self._last_trusted_name = name
        
        welcome = f"Welcome back, {name}!"
        print(f"🎉 {welcome}")
        self.tts.speak(welcome, mode=VoiceMode.FRIENDLY)
        
        self.in_trusted_conversation = True
        self.last_speech_time = time.time()
        
        if self.llm_agent:
            self.llm_agent.trusted_conversation_history = []
        
        self.speech.state = SystemState.TRUSTED_CONVERSATION
        self.speech.configure_for_mode()
        self.speech.needs_restart = True
        
        print(f"💬 Conversation active. Say 'bye' to end.")
        
        self.start_conversation_timeout()
    
    def handle_unknown_person(self, frame):
        """Handle unknown person"""
        if self.in_conversation or self.in_trusted_conversation:
            return
        
        print(f"\n{'='*70}")
        print(f"⚠️ UNKNOWN PERSON")
        print(f"{'='*70}\n")
        
        # Log as unknown initially
        self.log_event("Unknown person detected - starting interrogation", "INTRUDER_DETECTED")
        
        # Save snapshot with "unknown" label initially
        self.save_snapshot(frame, "unknown")
        
        self.in_conversation = True
        self.current_intruder = "unknown"
        self.current_intruder_name = None
        
        if self.llm_agent:
            initial = self.llm_agent.start_interaction()
            print(f"🤖 [Guard]: {initial}")
            self.tts.speak(initial, mode=VoiceMode.NORMAL)
        
        self.speech.state = SystemState.GUARD_MODE
        self.speech.configure_for_mode()
        self.speech.needs_restart = True
    
    def handle_intruder_speech(self, intruder_text):
        """Handle intruder speech"""
        if not self.in_conversation:
            return
        
        print(f"\n👤 [Intruder]: {intruder_text}")
        
        # Get recent events and enrolled names for LLM context
        recent_events = self.get_recent_events(limit=5)
        enrolled_names = list(self.face_db.keys()) if self.face_db else []
        
        # Process with LLM (now with events and enrolled names)
        if self.llm_agent:
            # Pass recent events and enrolled names to LLM
            response, should_continue, alarm, intruder_name = self.llm_agent.process_intruder_response(
                intruder_text,
                recent_events=recent_events,
                enrolled_names=enrolled_names
            )
            
            # Update intruder name if extracted
            if intruder_name and not self.current_intruder_name:
                self.current_intruder_name = intruder_name
                # Log the name extraction
                self.log_event(f"Intruder identified as: {intruder_name}", "INTRUDER_NAME_EXTRACTED")
            
            # Log the speech with name if available
            if self.current_intruder_name:
                self.log_event(f"Intruder ({self.current_intruder_name}) said: '{intruder_text}'", "INTRUDER_SPEECH")
            else:
                self.log_event(f"Intruder said: '{intruder_text}'", "INTRUDER_SPEECH")
            
            if alarm:
                self.trigger_alarm()
                self.in_conversation = False
                self.llm_agent.reset()
            elif not should_continue:  # Accepted or rejected
                # Check if was accepted
                summary = self.llm_agent.get_conversation_summary()
                accepted_label = self.current_intruder_name if self.current_intruder_name else "Visitor"
                
                if summary['escalation_level'] == 'LEVEL_1_INQUIRY':
                    # Was accepted at Level 1
                    self.log_event(f"Intruder accepted: {accepted_label}", "INTRUDER_ACCEPTED")
                else:
                    # Was rejected (escalated)
                    self.log_event(f"Intruder rejected: {accepted_label}", "INTRUDER_REJECTED")
                
                self.in_conversation = False
                self.current_intruder_name = None
                self.llm_agent.reset()
    
    def handle_trusted_speech(self, trusted_text):
        """Handle trusted speech"""
        self.last_speech_time = time.time()
        
        print(f"\n💬 [Trusted]: {trusted_text}")
        
        goodbye = ['bye', 'goodbye', 'see you', 'later', 'thank you', 'thanks', 'done']
        
        if any(phrase in trusted_text.lower() for phrase in goodbye):
            response = "Goodbye! Resuming monitoring."
            print(f"🤖 [Guard]: {response}")
            self.tts.speak(response, mode=VoiceMode.FRIENDLY)
            self.end_trusted_conversation()
            return
        
        response = self.generate_friendly_response(trusted_text)
        print(f"🤖 [Guard]: {response}")
        self.tts.speak(response, mode=VoiceMode.FRIENDLY)
    
    def generate_friendly_response(self, user_text):
        """Generate friendly response"""
        if self.llm_agent and self.llm_agent.llm_available:
            try:
                history_context = ""
                if self.llm_agent.trusted_conversation_history:
                    history_context = "\n\nConversation history:\n"
                    for user_msg, agent_msg in self.llm_agent.trusted_conversation_history[-5:]:
                        history_context += f"User: {user_msg}\nGuard: {agent_msg}\n"
                
                # Get last 5 events instead of last 1
                recent_events = self.get_recent_events(limit=5)
                event_context = ""
                if recent_events:
                    event_context = "\n\nRecent room activity (last 5 events):\n"
                    for event in recent_events:
                        event_context += f"[{event['timestamp']}] {event['type']}: {event['message']}\n"
                
                query_lower = user_text.lower()
                asking_about_visitors = any(word in query_lower for word in [
                    'anyone', 'someone', 'visitor', 'came', 'intruder', 'person', 
                    'who', 'been here', 'while i was', 'in my absence'
                ])
                
                prompt = f"""You are a friendly AI room guard. Casual conversation with trusted person.

Guidelines:
- Be warm and helpful
- Keep responses brief (1-2 sentences, under 25 words)
- Use conversation history for context
- If asked about visitors/intruders, refer to event logs below{history_context}{event_context}

User: "{user_text}"

Your response:"""
                
                result = self.llm_agent.model.generate_content(prompt)
                response = result.text.strip().strip('"').strip("'")
                
                self.llm_agent.trusted_conversation_history.append((user_text, response))
                
                return response
                
            except Exception as e:
                print(f"[LLM Error]: {e}")
        
        # Fallback
        text_lower = user_text.lower()
        
        if any(word in text_lower for word in ['anyone', 'visitor', 'came', 'intruder']):
            # Check last 5 events for intruders
            recent = self.get_recent_events(limit=5)
            intruder_events = [e for e in recent if 'INTRUDER' in e['type']]
            if intruder_events:
                return f"Yes, there was an unrecognized person at {intruder_events[-1]['timestamp']}."
            else:
                return "No visitors while you were away. All clear!"
        
        if 'how are you' in text_lower or 'whats up' in text_lower:
            return "I'm doing great! Just keeping your room safe."
        
        return "I'm here keeping your room safe! Feel free to chat."
    
    def start_conversation_timeout(self):
        """Start timeout monitor"""
        self.timeout_active = True
        self.timeout_thread = threading.Thread(target=self.conversation_timeout_monitor, daemon=True)
        self.timeout_thread.start()
    
    def conversation_timeout_monitor(self):
        """Monitor for timeout"""
        print(f"[Timeout Monitor] Started - {CONVERSATION_TIMEOUT}s")
        
        while self.timeout_active and self.in_trusted_conversation:
            time.sleep(1)
            
            silence = time.time() - self.last_speech_time
            
            if silence >= CONVERSATION_TIMEOUT:
                print(f"\n[Timeout Monitor] {CONVERSATION_TIMEOUT}s silence - ending conversation\n")
                self.end_trusted_conversation()
                msg = "Conversation timed out. Resuming monitoring."
                self.tts.speak(msg, mode=VoiceMode.NORMAL)
                break
        
        print("[Timeout Monitor] Stopped")
    
    def end_trusted_conversation(self):
        """End conversation and resume monitoring"""
        print(f"\n{'='*70}")
        print("💬 ENDING CONVERSATION - Resuming monitoring")
        print(f"{'='*70}\n")
        
        self.in_trusted_conversation = False
        self.timeout_active = False
        
        self.speech.state = SystemState.GUARD_MODE
        self.speech.configure_for_mode()
        self.speech.needs_restart = True
        
        self.recognition_buffer.clear()
        self.last_detected_person = getattr(self, '_last_trusted_name', None)
        self.last_action_time = time.time()
        
        print("✅ Face monitoring RESUMED")
    
    def trigger_alarm(self):
        """Trigger alarm"""
        print(f"\n{'🚨'*35}")
        print("🚨 ALARM TRIGGERED - INTRUDER REFUSED TO COOPERATE 🚨")
        print(f"{'🚨'*35}\n")
        
        alarm = "ALARM! ALARM! Security breach! Authorities notified! Leave immediately!"
        print(f"🚨 {alarm}")
        self.tts.speak(alarm, mode=VoiceMode.ALERT)
        
        intruder_label = self.current_intruder_name if self.current_intruder_name else "Unknown"
        self.log_event(f"ALARM TRIGGERED - Intruder ({intruder_label}) refused to cooperate", "ALARM")
    
    def save_snapshot(self, frame, label):
        """Save snapshot - uses intruder name if available"""
        os.makedirs(SNAP_DIR, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        # If it's an unknown person and we have their name, use it
        if label == "unknown" and self.current_intruder_name:
            label = f"Unknown ({self.current_intruder_name})"
        
        filename = os.path.join(SNAP_DIR, f"{label}_{timestamp}.jpg")
        cv2.imwrite(filename, frame)
        print(f"📸 Snapshot: {filename}")
        self.log_event(f"Snapshot: {label} -> {filename}", "SNAPSHOT")
        return filename
    
    def log_event(self, message, event_type="INFO"):
        """Log events to file and memory"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = {
            'timestamp': timestamp,
            'type': event_type,
            'message': message
        }
        
        # Add to memory
        self.event_log.append(log_entry)
        
        # Keep last 50 in memory
        if len(self.event_log) > 50:
            self.event_log = self.event_log[-50:]
        
        # Write to file
        log_file = "events.log"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} | [{event_type}] {message}\n")
    
    def get_recent_events(self, limit=5):
        """Get last N events for context"""
        return self.event_log[-limit:] if len(self.event_log) >= limit else self.event_log


# ==================== MAIN ENTRY POINT ====================

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="AI Room Guard System - EE782 Project (Enhanced)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Voice Commands:
  - "Guard Mode On"  : Activate room monitoring
  - "Guard Mode Off" : Deactivate monitoring
  - "Enroll"         : Add new trusted person

Enhanced Features:
  - Time-based intruder acceptance (5+ questions, 60+ seconds, ONLY at Level 1)
  - Once escalated to Level 2+, intruders cannot be accepted
  - Improved event logging with intruder names
  - Query last 5 events for better context
  - Automatic name extraction from intruder responses

Setup:
  1. Set API key: export GEMINI_API_KEY='your-key-here'
  2. Install dependencies
  3. Run: python main_guard_system.py
        """
    )
    
    parser.add_argument('--api-key', help='API key for Gemini')
    parser.add_argument('--timeout', type=float, default=30.0, help='Conversation timeout (default: 30s)')
    
    args = parser.parse_args()
    
    global CONVERSATION_TIMEOUT
    CONVERSATION_TIMEOUT = args.timeout
    
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║          🛡️ AI ROOM GUARD SYSTEM - EE782 🛡️                  ║
    ║                                                              ║
    ║  Enhanced Features:                                          ║
    ║  ✓ Level 1 only acceptance (5+ questions, 60+ seconds)      ║
    ║  ✓ Intruder name extraction and logging                     ║
    ║  ✓ Query last 5 events for better context                   ║
    ║  ✓ Cannot accept after escalation                           ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    try:
        guard = AIRoomGuard(
            llm_provider="gemini",
            api_key=args.api_key
        )
        
        guard.start()
    
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()