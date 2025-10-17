# AI-room-guard-agent
# 🛡️ AI Room Guard System

**EE782 Course Project - Multimodal AI Security Agent**

An intelligent room security system that seamlessly integrates computer vision, speech recognition, and large language models to provide autonomous monitoring and intelligent intruder interrogation.

---

## 📋 Table of Contents
- [Contributors](#contributors)
- [Demo & Documentation](#demo--documentation)
- [Features](#features)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Voice Commands](#voice-commands)
- [Troubleshooting](#troubleshooting)


---
## 👥 Contributors

**[Saptarshi Biswas]**  Roll No: [22B1258]  
**[Hardik Gohil]**  Roll No: [22B1293]  
Department of Electrical Engineering  
Indian Institute of Technology

---
## 🎬 Demo & Documentation

### 📂 Google Drive Link
**Access all project materials:**

🔗 **[AI Room Guard - Google Drive Link](https://drive.google.com/drive/folders/1dZWImLHd79YLuh4QIpff5y13IcPj-VlT?usp=drive_link)**

**Contents:**
- 📹 **Demonstration Video** - Working of our model
- 🎥 **Explanation Video** -  Full system walkthrough
- 📄 **Project Report (PDF)** - Documentation
- 📁 **Source Code** - Complete implementation files

---

## ✨ Features

### Core Capabilities
- 🎥 **Real-time Face Recognition** - Identifies trusted persons with 87% accuracy
- 🎤 **Voice-Activated Controls** - Hands-free operation via natural voice commands
- 🤖 **LLM-Powered Conversations** - Intelligent intruder interrogation using Google Gemini
- 📊 **4-Level Escalation System** - Progressive responses from polite inquiry to alarm
- 🔐 **Impersonation Detection** - Cross-modal verification prevents identity spoofing
- 📝 **Comprehensive Logging** - Detailed audit trail with timestamps and identities

### Advanced Features
- ⏱️ **Time-Based Acceptance** - Cooperative intruders can gain access (Level 1 only)
- 🗣️ **Context-Aware Responses** - Memory of conversation history and recent events
- 🎯 **Multi-Pose Enrollment** - 6 photos captured automatically with voice guidance
- 🔊 **Adaptive Voice Modes** - Normal, Friendly, and Alert TTS modes
- 💬 **Trusted Conversations** - Chat with the guard about room activity

---

## 🚀 Quick Start

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd ai-room-guard

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/macOS

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up API key
set GEMINI_API_KEY=your-api-key-here  # Windows
# export GEMINI_API_KEY=your-api-key-here  # Linux/macOS

# 5. Run the system
python main_guard_system.py
```

---

## 📦 Installation

### Step 1: Install Python Dependencies

```bash
pip install -r requirements.txt
```

**Note:** On Windows, dlib is installed automatically from a pre-built wheel. On Linux/macOS, install system dependencies first:

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install python3-dev cmake portaudio19-dev
```

**macOS:**
```bash
brew install cmake portaudio
```

### Step 2: Get Gemini API Key

1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create a new API key
3. Set environment variable:

```bash
# Windows
set GEMINI_API_KEY=your-api-key-here

# Linux/macOS
export GEMINI_API_KEY=your-api-key-here
```

### Step 3: Verify Installation

```bash
python -c "import face_recognition; print('✓ Face recognition ready')"
python -c "import speech_recognition; print('✓ Speech recognition ready')"
python -c "import cv2; print('✓ OpenCV ready')"
```

---

## 🎮 Usage

### First-Time Setup

1. **Enroll Yourself**
   ```
   Say: "Enroll"
   System: "Please say the name of the person to enroll."
   Say: "John Smith"
   [System captures 6 photos automatically with pose guidance]
   ```

2. **Activate Guard Mode**
   ```
   Say: "Guard mode on"
   [System starts monitoring]
   ```

3. **Test Recognition**
   - Stand in front of camera
   - System recognizes you: "Welcome back, John Smith!"
   - Can chat with the guard
   - Say "bye" to exit conversation

4. **Test Intruder Detection**
   - Have someone else approach
   - System starts interrogation
   - Observe escalation behavior

5. **Deactivate**
   ```
   Say: "Guard mode off"
   ```

---

## 📁 Project Structure

```
AI-ROOM-GUARD/
│
├── main_guard_system.py          # Main orchestrator
├── EnhancedSpeechRecognition.py  # Speech recognition module
├── LLMConversationAgent.py       # LLM conversation logic
├── TexttoSpeech.py               # TTS output module
├── VoiceEnrollment.py            # Enrollment system
│
├── requirements.txt               # Python dependencies
├── README.md                      # This file
├── EE782 ASSIGMENT 2 REPORT.pdf   # Technical report
│
├── embeddings.pkl                 # Face database (generated)
├── events.log                     # System event log (generated)
│
├── snapshots/                     # Captured images
└── captures/                      # Enrollment photos
```

---

## 🎤 Voice Commands

| Command | Description |
|---------|-------------|
| **"Enroll"** | Start enrollment process for new trusted person |
| **"Guard mode on"** | Activate room monitoring |
| **"Guard mode off"** | Deactivate monitoring and return to idle |
| **"Bye"** / **"Goodbye"**| Exit trusted conversation mode |

---

## 🔧 Troubleshooting

### Microphone Not Detected
```bash
# Check available microphones
python -c "import speech_recognition as sr; print(sr.Microphone.list_microphone_names())"
```
**Solution:** Grant microphone permissions to Terminal/Python

### Cannot Open Webcam
**Solution:** 
- Close other applications using webcam (Zoom, Teams, etc.)
- Grant camera permissions
- Try different camera index in code (0, 1, 2)

### Speech Recognition Errors
**Solution:**
- Check internet connection (Google Speech API requires internet)
- Speak clearly with pauses between commands
- Reduce background noise
- Adjust `energy_threshold` in `EnhancedSpeechRecognition.py`

### LLM Not Responding
**Solution:**
- Verify `GEMINI_API_KEY` is set correctly
- Check API status at [Google AI](https://ai.google.dev/)
- System falls back to rule-based responses if LLM unavailable

### Face Recognition Too Sensitive/Lenient
**Solution:** Adjust threshold in `main_guard_system.py`:
```python
RECOGNITION_THRESHOLD = 0.4  # Lower = stricter (try 0.35)
                             # Higher = lenient (try 0.5)
```

---

## 🎓 Academic Context

**Course:** EE782 - [Advanced Topics in Machine Learning]  
**Institution:** Indian Institute of Technology  
**Project Type:** Multimodal AI Security Agent  
**Submission Date:** [13/10/2025]

---

## 📄 License

This project is submitted as part of academic coursework for EE782.

---

