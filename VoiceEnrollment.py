"""
VoiceEnrollment.py

Voice-activated face enrollment system.
No keyboard required - all interactions via voice.
"""

import os
import time
import cv2
import face_recognition
import numpy as np
import pickle
from TexttoSpeech import SimpleTTS, VoiceMode

EMB_FILE = "embeddings.pkl"
SNAP_DIR = "captures"

class VoiceEnrollment:
    """Handle voice-activated face enrollment"""
    
    def __init__(self, tts=None):
        self.tts = tts if tts else SimpleTTS()
        self.enrollment_active = False
        self.person_name = None
        self.photos_taken = 0
        self.target_photos = 6
        self.enrollment_complete = False
    
    def start_enrollment(self):
        """Start the enrollment process"""
        self.enrollment_active = True
        self.person_name = None
        self.photos_taken = 0
        self.enrollment_complete = False
        
        message = "Enrollment mode activated. Please say the name of the person to enroll."
        print(f"\n[Enrollment] {message}")
        self.tts.speak(message, mode=VoiceMode.NORMAL)
        
        return message
    
    def set_person_name(self, name):
        """Set the name for enrollment"""
        # Clean up the name
        self.person_name = name.strip().title()
        
        message = f"Enrolling {self.person_name}. Please look at the camera. I will take {self.target_photos} photos automatically."
        print(f"\n[Enrollment] {message}")
        self.tts.speak(message, mode=VoiceMode.NORMAL)
        
        time.sleep(1)
        self.tts.speak("Get ready. Starting in 3, 2, 1", mode=VoiceMode.NORMAL)
        time.sleep(2)
        
        return message
    
    def capture_photos_from_webcam(self):
        """Capture photos automatically from webcam"""
        os.makedirs(SNAP_DIR, exist_ok=True)
        
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            error_msg = "Cannot open webcam"
            print(f"[Enrollment ERROR] {error_msg}")
            self.tts.speak(error_msg, mode=VoiceMode.ALERT)
            return []
        
        print(f"\n[Enrollment] Starting automatic capture of {self.target_photos} photos")
        
        captured_paths = []
        self.photos_taken = 0
        
        # Auto-capture photos with intervals
        capture_interval = 1.5  # seconds between captures
        last_capture_time = 0
        
        instructions = [
            "Face forward",
            "Turn slightly left",
            "Turn slightly right", 
            "Look up a little",
            "Look down a little",
            "Back to center"
        ]
        
        while self.photos_taken < self.target_photos:
            ret, frame = cap.read()
            if not ret:
                break
            
            current_time = time.time()
            
            # Display frame with instructions
            display_frame = frame.copy()
            progress_text = f"Photos: {self.photos_taken}/{self.target_photos}"
            instruction_text = instructions[min(self.photos_taken, len(instructions)-1)]
            
            cv2.putText(display_frame, progress_text, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
            cv2.putText(display_frame, instruction_text, (10, 70),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)
            
            # Draw face detection box if detected
            small = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
            rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            locs = face_recognition.face_locations(rgb)
            
            if locs:
                for (t, r, b, l) in locs:
                    top, right, bottom, left = [v * 2 for v in (t, r, b, l)]
                    cv2.rectangle(display_frame, (left, top), (right, bottom), (0, 255, 0), 2)
            
            cv2.imshow("Enrollment - Capturing Photos", display_frame)
            
            # Auto-capture at intervals
            if current_time - last_capture_time >= capture_interval:
                if locs:  # Only capture if face detected
                    fname = os.path.join(SNAP_DIR, 
                                        f"{self.person_name}_{int(time.time())}_{self.photos_taken}.jpg")
                    cv2.imwrite(fname, frame)
                    captured_paths.append(fname)
                    
                    print(f"[Enrollment] ✓ Photo {self.photos_taken + 1}/{self.target_photos} captured")
                    self.tts.speak(instruction_text, mode=VoiceMode.NORMAL)
                    
                    self.photos_taken += 1
                    last_capture_time = current_time
                else:
                    print("[Enrollment] ⚠ No face detected, waiting...")
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        cap.release()
        cv2.destroyAllWindows()
        for _ in range(5):
            cv2.waitKey(1)
        
        return captured_paths
    
    def process_enrollment(self, image_paths):
        """Process captured images and save embeddings"""
        if not image_paths:
            error_msg = "No photos captured. Enrollment failed."
            print(f"[Enrollment ERROR] {error_msg}")
            self.tts.speak(error_msg, mode=VoiceMode.ALERT)
            return False
        
        print(f"\n[Enrollment] Processing {len(image_paths)} photos...")
        self.tts.speak("Processing photos", mode=VoiceMode.NORMAL)
        
        embeddings = []
        successful = 0
        
        for path in image_paths:
            embedding = self._get_face_embedding(path)
            if embedding is not None:
                embeddings.append(embedding)
                successful += 1
                print(f"[Enrollment] ✓ Extracted embedding from {os.path.basename(path)}")
        
        if successful == 0:
            error_msg = "Could not extract face data from photos. Please try again."
            print(f"[Enrollment ERROR] {error_msg}")
            self.tts.speak(error_msg, mode=VoiceMode.ALERT)
            return False
        
        # Load existing database
        db = self._load_embeddings()
        
        # Add new embeddings
        if self.person_name not in db:
            db[self.person_name] = []
        db[self.person_name].extend(embeddings)
        
        # Save database
        self._save_embeddings(db)
        
        success_msg = f"Successfully enrolled {self.person_name} with {successful} photos. Enrollment complete."
        print(f"\n[Enrollment] ✓ {success_msg}")
        self.tts.speak(success_msg, mode=VoiceMode.FRIENDLY)
        
        self.enrollment_complete = True
        self.enrollment_active = False
        
        return True
    
    def _get_face_embedding(self, image_path):
        """Extract face embedding from image"""
        try:
            img = face_recognition.load_image_file(image_path)
            locs = face_recognition.face_locations(img)
            
            if not locs:
                return None
            
            encs = face_recognition.face_encodings(img, locs)
            if not encs:
                return None
            
            # If multiple faces, use the largest one
            if len(locs) > 1:
                areas = [(b-t)*(r-l) for (t,r,b,l) in locs]
                idx = int(np.argmax(areas))
                return encs[idx]
            
            return encs[0]
        except Exception as e:
            print(f"[Enrollment ERROR] Failed to process {image_path}: {e}")
            return None
    
    def _load_embeddings(self):
        """Load existing embeddings database"""
        if os.path.exists(EMB_FILE):
            with open(EMB_FILE, "rb") as f:
                raw = pickle.load(f)
            return {name: [np.array(e) for e in arr] for name, arr in raw.items()}
        return {}
    
    def _save_embeddings(self, db):
        """Save embeddings database"""
        serial = {name: [e.tolist() for e in arr] for name, arr in db.items()}
        with open(EMB_FILE, "wb") as f:
            pickle.dump(serial, f)
        print(f"[Enrollment] ✓ Saved to {EMB_FILE}")
    
    def cancel_enrollment(self):
        """Cancel ongoing enrollment"""
        self.enrollment_active = False
        self.enrollment_complete = False
        message = "Enrollment cancelled"
        print(f"\n[Enrollment] {message}")
        self.tts.speak(message, mode=VoiceMode.NORMAL)
    
    def is_active(self):
        """Check if enrollment is active"""
        return self.enrollment_active
    
    def is_complete(self):
        """Check if enrollment is complete"""
        return self.enrollment_complete
    
    def reset(self):
        """Reset enrollment state"""
        self.enrollment_active = False
        self.person_name = None
        self.photos_taken = 0
        self.enrollment_complete = False


# Test function
def test_voice_enrollment():
    """Test the voice enrollment system"""
    import sys
    
    tts = SimpleTTS()
    enrollm = VoiceEnrollment(tts)
    
    print("Testing Voice Enrollment System")
    print("="*60)
    
    # Start enrollment
    enrollm.start_enrollment()
    
    # Get name from user
    name = input("\nEnter name to test (or 'cancel'): ").strip()
    if name.lower() == 'cancel':
        enrollm.cancel_enrollment()
        sys.exit(0)
    
    enrollm.set_person_name(name)
    
    # Capture photos
    photos = enrollm.capture_photos_from_webcam()
    
    # Process enrollment
    if photos:
        success = enrollm.process_enrollment(photos)
        print(f"\nEnrollment {'SUCCESS' if success else 'FAILED'}")
    
    tts.quit()

if __name__ == "__main__":
    test_voice_enrollment()