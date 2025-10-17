"""
LLMConversationAgent.py - COMPLETE FIXED VERSION

Features:
1. Wrong name detection - auto-escalates if intruder claims to be enrolled person
2. Receives last 5 event logs for context
3. Receives enrolled names list
4. Shows current intruder identity to LLM
5. Time-based acceptance ONLY at Level 1
"""

import os
import time
import re
from enum import Enum

# Gemini integration
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("[ERROR] google-generativeai not installed. Run: pip install google-generativeai")


class EscalationLevel(Enum):
    """Escalation levels for intruder interaction"""
    LEVEL_1_INQUIRY = 1      # Polite inquiry
    LEVEL_2_SUSPICION = 2    # Firm questioning with suspicion
    LEVEL_3_WARNING = 3      # Direct warning
    LEVEL_4_ALERT = 4        # Final threat/alarm


class LLMConversationAgent:
    """Manages conversations with intruders using Gemini LLM"""
    
    def __init__(self, api_key=None, tts=None):
        """Initialize the conversation agent"""
        self.tts = tts
        self.model = None
        self.llm_available = False
        
        # Conversation state
        self.escalation_level = EscalationLevel.LEVEL_1_INQUIRY
        self.conversation_history = []
        self.start_time = None
        self.response_count = 0
        self.evasion_count = 0
        self.hostile_count = 0
        self.cooperative_count = 0
        
        # Track intruder's stated identity
        self.intruder_claimed_name = None
        self.intruder_claimed_reason = None
        
        # Trusted conversation history
        self.trusted_conversation_history = []
        
        # Initialize Gemini
        self._initialize_gemini(api_key)
        
        print(f"[LLM] Conversation agent initialized with wrong name detection")
    
    def _initialize_gemini(self, api_key):
        """Initialize Gemini model"""
        if not GEMINI_AVAILABLE:
            print("[LLM] WARNING: Using fallback responses (Gemini not available)")
            return
        
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            print("[LLM] WARNING: GEMINI_API_KEY not found. Using fallback responses.")
            return
        
        try:
            genai.configure(api_key=key)
            
            models_to_try = [
                'gemini-2.0-flash-exp',
                'gemini-2.5-flash',
                'gemini-2.5-pro',
                'gemini-pro'
            ]
            
            for model_name in models_to_try:
                try:
                    self.model = genai.GenerativeModel(model_name)
                    test = self.model.generate_content("Hello")
                    if test and test.text:
                        self.llm_available = True
                        print(f"[LLM] ✓ Using Gemini model: {model_name}")
                        return
                except:
                    continue
            
            print("[LLM] WARNING: Could not initialize any Gemini model. Using fallbacks.")
            
        except Exception as e:
            print(f"[LLM] ERROR: Gemini initialization failed: {e}")
    
    def start_interaction(self):
        """Start a new interaction with an intruder"""
        self.escalation_level = EscalationLevel.LEVEL_1_INQUIRY
        self.conversation_history = []
        self.start_time = time.time()
        self.response_count = 0
        self.evasion_count = 0
        self.hostile_count = 0
        self.cooperative_count = 0
        self.intruder_claimed_name = None
        self.intruder_claimed_reason = None
        
        print(f"\n{'='*70}")
        print("[INTRUDER DETECTED] Starting conversation")
        print(f"{'='*70}\n")
        
        initial_message = self._generate_initial_greeting()
        self.conversation_history.append(("AGENT", initial_message))
        
        return initial_message
    
    def process_intruder_response(self, intruder_text, recent_events=None, enrolled_names=None):
        """
        Process intruder's response with full context.
        
        Args:
            intruder_text: What the intruder said
            recent_events: List of recent event logs (last 5)
            enrolled_names: List of enrolled trusted person names
            
        Returns:
            tuple: (agent_response, should_continue, should_alarm, intruder_name)
        """
        if not intruder_text or len(intruder_text.strip()) == 0:
            return None, True, False, None
        
        print(f"\n[Intruder]: {intruder_text}")
        
        # Add to history
        self.conversation_history.append(("INTRUDER", intruder_text))
        self.response_count += 1
        
        # Extract name if mentioned
        extracted_name = self._extract_name_from_text(intruder_text)
        if extracted_name and not self.intruder_claimed_name:
            self.intruder_claimed_name = extracted_name
            print(f"   [INFO] Extracted name: {extracted_name}")
            
            # CRITICAL: Check if they're claiming to be an enrolled person
            if enrolled_names and extracted_name in enrolled_names:
                print(f"   [WARNING] Intruder claims to be enrolled person '{extracted_name}' but wasn't recognized!")
                print(f"   [ACTION] Auto-escalating due to suspicious identity claim")
                self._escalate()
                suspicious_response = f"Wait a moment. You say you're {extracted_name}, but my facial recognition didn't identify you. That's very suspicious. Explain yourself now!"
                self.conversation_history.append(("AGENT", suspicious_response))
                if self.tts:
                    from TexttoSpeech import VoiceMode
                    self.tts.speak(suspicious_response, mode=VoiceMode.ALERT)
                print(f"[Guard]: {suspicious_response}")
                print(f"[Status] Level: {self.escalation_level.name} (AUTO-ESCALATED)")
                return suspicious_response, True, False, extracted_name
        
        # Generate response using LLM or fallback
        if self.llm_available:
            agent_response, accepted = self._llm_respond(intruder_text, recent_events, enrolled_names)
        else:
            agent_response, accepted = self._rule_based_respond(intruder_text, enrolled_names)
        
        # Add agent response to history
        self.conversation_history.append(("AGENT", agent_response))
        
        # Speak the response
        if self.tts and agent_response:
            from TexttoSpeech import VoiceMode
            mode = self._get_voice_mode()
            self.tts.speak(agent_response, mode=mode)
        
        print(f"[Guard]: {agent_response}")
        print(f"[Status] Level: {self.escalation_level.name}, Responses: {self.response_count}, "
              f"Cooperative: {self.cooperative_count}, Evasive: {self.evasion_count}")
        
        # Check if we should alarm
        should_alarm = self.escalation_level == EscalationLevel.LEVEL_4_ALERT
        should_continue = not (accepted or should_alarm)
        
        return agent_response, should_continue, should_alarm, self.intruder_claimed_name
    
    def _generate_initial_greeting(self):
        """Generate the initial greeting to the intruder"""
        greetings = [
            "Hello! I don't recognize you. Who are you and what brings you here?",
            "Excuse me, I haven't seen you before. May I know your name and why you're here?",
            "Hi there. I don't believe we've met. Can you tell me who you are?",
        ]
        import random
        return random.choice(greetings)
    
    def _llm_respond(self, intruder_text, recent_events=None, enrolled_names=None):
        """Use Gemini LLM with full context"""
        # Build conversation history
        history_text = "\n".join([f"{role}: {text}" for role, text in self.conversation_history])
        
        # Calculate conversation duration
        elapsed_time = int(time.time() - self.start_time)
        
        # Build event log context
        event_context = ""
        if recent_events:
            event_context = "\n\nRECENT ROOM ACTIVITY (Last 5 events):\n"
            for event in recent_events:
                event_context += f"[{event['timestamp']}] {event['type']}: {event['message']}\n"
        
        # Build enrolled names context
        enrolled_context = ""
        if enrolled_names:
            enrolled_context = f"\n\nENROLLED TRUSTED PERSONS: {', '.join(enrolled_names)}\n"
        
        # Current intruder identity
        intruder_identity = f"\n\nCURRENT INTRUDER IDENTITY: {self.intruder_claimed_name if self.intruder_claimed_name else 'Not yet stated'}\n"
        
        # Create comprehensive prompt
        prompt = f"""You are an AI security guard protecting a room. An unrecognized person is present.

Current escalation level: {self.escalation_level.name}
Time elapsed: {elapsed_time} seconds
Response count: {self.response_count}
Cooperative responses: {self.cooperative_count}
Evasive responses: {self.evasion_count}
Hostile responses: {self.hostile_count}{enrolled_context}{intruder_identity}{event_context}

Conversation so far:
{history_text}

Analyze the intruder's last response: "{intruder_text}"

**CRITICAL: NAME VERIFICATION CHECK**
- If the intruder mentions being a trusted person (e.g., "I'm John", "It's me, Sarah")
- Check if that name is in the ENROLLED TRUSTED PERSONS list above
- If they claim to be an enrolled person BUT face recognition didn't recognize them:
  → This is HIGHLY SUSPICIOUS - ESCALATE IMMEDIATELY
  → They might be lying or trying to impersonate someone
- If they mention someone else's name (e.g., "waiting for John") verify John is enrolled

**WRONG NAME EXAMPLES TO ESCALATE**:
- Intruder: "I'm Hardik" BUT Hardik is enrolled (face should have recognized them)
- Intruder: "I'm Sarah" BUT Sarah is not in enrolled list
- Intruder: "Waiting for Bob" BUT Bob is not enrolled
→ All these should ESCALATE

ACCEPTANCE CRITERIA:

**IMMEDIATE ACCEPTANCE** (ONLY at Level 1):
- Clear relationship: "I'm [owner's] friend/roommate" (where owner IS enrolled)
- Legitimate purpose: "Here to pick up notes for [enrolled person]"
- Waiting for enrolled person with valid name
- Quick errand with specific item mentioned

**TIME-BASED ACCEPTANCE** (ONLY AT LEVEL 1):
- 5+ cooperative responses AND 60+ seconds AND still at Level 1
- CRITICAL: Once escalated to Level 2+, acceptance is NOT possible

**ESCALATION CRITERIA**:
- **Claims to be enrolled person but wasn't recognized** → ESCALATE IMMEDIATELY
- **Mentions waiting for non-enrolled person** → ESCALATE
- Hostile/rude → ESCALATE immediately
- Evasive after 2-3 exchanges → ESCALATE
- More than 4 exchanges without details → ESCALATE

**YOUR TASK**:
1. **CHECK NAME VERIFICATION FIRST**
2. Classify: COOPERATIVE, EVASIVE, or HOSTILE
3. Decide: ACCEPT (ONLY at Level 1), MAINTAIN, or ESCALATE
4. Generate natural response (1-2 sentences)

Format EXACTLY as:
RESPONSE_TYPE: [COOPERATIVE/EVASIVE/HOSTILE]
ESCALATION_DECISION: [ACCEPT/MAINTAIN/ESCALATE]
NEXT_RESPONSE: [your response]"""

        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Parse response
            lines = response_text.split('\n')
            response_type = None
            decision = None
            next_response = None
            
            for line in lines:
                if 'RESPONSE_TYPE:' in line.upper():
                    response_type = line.split(':', 1)[1].strip().upper()
                elif 'ESCALATION_DECISION:' in line.upper():
                    decision = line.split(':', 1)[1].strip().upper()
                elif 'NEXT_RESPONSE:' in line.upper():
                    next_response = line.split(':', 1)[1].strip()
                    next_response = next_response.strip('"').strip("'")
            
            # Track response type
            if response_type == 'COOPERATIVE':
                self.cooperative_count += 1
            elif response_type == 'EVASIVE':
                self.evasion_count += 1
            elif response_type == 'HOSTILE':
                self.hostile_count += 1
            
            # Time-based acceptance check (ONLY at Level 1)
            if (self.cooperative_count >= 5 and elapsed_time >= 60 and 
                self.escalation_level == EscalationLevel.LEVEL_1_INQUIRY):
                print(f"   → TIME-BASED ACCEPTANCE (5+ cooperative, 60+ seconds, Level 1)")
                return "You've answered my questions well. I'll grant you access. Welcome!", True
            
            # Apply escalation decision
            if decision == 'ESCALATE':
                self._escalate()
                print(f"   → ESCALATED to {self.escalation_level.name}")
            elif decision == 'ACCEPT':
                # ONLY accept if still at LEVEL_1
                if self.escalation_level == EscalationLevel.LEVEL_1_INQUIRY:
                    print(f"   → ACCEPTED (legitimate, Level 1)")
                    return next_response if next_response else "Okay, welcome!", True
                else:
                    print(f"   → CANNOT ACCEPT (already at {self.escalation_level.name})")
                    return "I appreciate your explanation, but you need to leave now.", False
            else:  # MAINTAIN
                print(f"   → MAINTAINED at {self.escalation_level.name}")
            
            if next_response:
                return next_response, False
            else:
                return self._get_fallback_response(), False
                
        except Exception as e:
            print(f"[LLM ERROR] {e}")
            return self._rule_based_respond(intruder_text, enrolled_names)
    
    def _rule_based_respond(self, intruder_text, enrolled_names=None):
        """Fallback rule-based system"""
        text_lower = intruder_text.lower()
        elapsed_time = time.time() - self.start_time
        
        # Check if intruder mentions an enrolled name
        if enrolled_names:
            for enrolled_name in enrolled_names:
                if f"i'm {enrolled_name.lower()}" in text_lower or f"i am {enrolled_name.lower()}" in text_lower:
                    print(f"   [WARNING] Claims to be enrolled '{enrolled_name}' - SUSPICIOUS!")
                    self._escalate()
                    return f"You claim to be {enrolled_name}, but you weren't recognized. That's suspicious. Explain now!", False
        
        # Keyword analysis
        hostile_keywords = ['none of your business', 'shut up', 'fuck', 'get lost']
        evasive_keywords = ['just looking', 'nothing', 'none', "doesn't matter"]
        legitimate_keywords = ['roommate', 'friend', 'invited', 'waiting for', 'pick up', 'drop off']
        cooperative_indicators = ['please', 'sorry', 'thank you']
        
        # Check patterns
        if any(keyword in text_lower for keyword in hostile_keywords):
            self.hostile_count += 1
            self._escalate()
            print(f"   → ESCALATED (hostile)")
        elif any(keyword in text_lower for keyword in legitimate_keywords):
            self.cooperative_count += 1
            if self.escalation_level == EscalationLevel.LEVEL_1_INQUIRY:
                print(f"   → ACCEPTED (legitimate, Level 1)")
                return "Okay, that makes sense. Come on in!", True
            else:
                print(f"   → CANNOT ACCEPT (already at {self.escalation_level.name})")
                return "I appreciate your explanation, but I still need you to leave.", False
        elif any(keyword in text_lower for keyword in evasive_keywords):
            self.evasion_count += 1
            if self.evasion_count >= 2:
                self._escalate()
                print(f"   → ESCALATED (evasion)")
        elif any(indicator in text_lower for indicator in cooperative_indicators):
            self.cooperative_count += 1
        elif len(intruder_text.strip()) > 15:
            self.cooperative_count += 1
        
        # Time-based acceptance (ONLY at Level 1)
        if (self.cooperative_count >= 5 and elapsed_time >= 60 and 
            self.escalation_level == EscalationLevel.LEVEL_1_INQUIRY):
            print(f"   → TIME-BASED ACCEPTANCE ({self.cooperative_count} cooperative, {int(elapsed_time)}s, Level 1)")
            return "You've been cooperative. I'll let you in. Welcome!", True
        elif self.cooperative_count >= 5 and elapsed_time >= 60:
            print(f"   → CANNOT ACCEPT ({self.cooperative_count} cooperative, but at {self.escalation_level.name})")
            return "I appreciate your cooperation, but you need to leave now.", False
        
        # Time/count based escalation
        if elapsed_time > 90 and self.escalation_level.value < 3:
            self._escalate()
            print(f"   → ESCALATED (time)")
        
        if self.response_count >= 7 and self.escalation_level == EscalationLevel.LEVEL_1_INQUIRY:
            self._escalate()
            print(f"   → ESCALATED (too many exchanges)")
        
        return self._get_fallback_response(), False
    
    def _extract_name_from_text(self, text):
        """Extract potential name from intruder's response"""
        text_lower = text.lower()
        
        # Pattern 1: "I'm [name]" or "I am [name]"
        match = re.search(r"i'?m\s+([a-z]+)", text_lower)
        if match:
            name = match.group(1).title()
            if len(name) > 2 and name not in ['Here', 'Just', 'The', 'From', 'With']:
                return name
        
        # Pattern 2: "My name is [name]"
        match = re.search(r"my name is\s+([a-z]+)", text_lower)
        if match:
            return match.group(1).title()
        
        # Pattern 3: "This is [name]"
        match = re.search(r"this is\s+([a-z]+)", text_lower)
        if match:
            name = match.group(1).title()
            if len(name) > 2:
                return name
        
        return None
    
    def _escalate(self):
        """Move to next escalation level"""
        if self.escalation_level.value < 4:
            self.escalation_level = EscalationLevel(self.escalation_level.value + 1)
    
    def _get_fallback_response(self):
        """Get pre-scripted response for current level"""
        responses = {
            EscalationLevel.LEVEL_1_INQUIRY: [
                "Can you please tell me your name and why you're in this room?",
                "I need to know who you are. This is a private room.",
            ],
            EscalationLevel.LEVEL_2_SUSPICION: [
                "I'm not satisfied with your answer. Who exactly are you here for?",
                "This room is monitored. Tell me exactly what you're doing here.",
            ],
            EscalationLevel.LEVEL_3_WARNING: [
                "This is your final warning. Leave this room immediately.",
                "Leave right now. This is private property and you're trespassing.",
            ],
            EscalationLevel.LEVEL_4_ALERT: [
                "Security alert! I'm calling the authorities right now!",
                "ALARM! Campus security is being notified! Leave immediately!",
            ]
        }
        
        import random
        return random.choice(responses.get(self.escalation_level, ["Please identify yourself."]))
    
    def _get_voice_mode(self):
        """Get appropriate voice mode for TTS"""
        from TexttoSpeech import VoiceMode
        
        if self.escalation_level == EscalationLevel.LEVEL_1_INQUIRY:
            return VoiceMode.NORMAL
        elif self.escalation_level == EscalationLevel.LEVEL_2_SUSPICION:
            return VoiceMode.NORMAL
        else:
            return VoiceMode.ALERT
    
    def should_trigger_alarm(self):
        """Check if alarm should be triggered"""
        return self.escalation_level == EscalationLevel.LEVEL_4_ALERT
    
    def reset(self):
        """Reset conversation state"""
        self.escalation_level = EscalationLevel.LEVEL_1_INQUIRY
        self.conversation_history = []
        self.trusted_conversation_history = []
        self.start_time = None
        self.response_count = 0
        self.evasion_count = 0
        self.hostile_count = 0
        self.cooperative_count = 0
        self.intruder_claimed_name = None
        self.intruder_claimed_reason = None
        print("[LLM] Conversation reset")
    
    def get_conversation_summary(self):
        """Get a summary of the conversation"""
        summary = {
            'escalation_level': self.escalation_level.name,
            'response_count': self.response_count,
            'evasion_count': self.evasion_count,
            'hostile_count': self.hostile_count,
            'cooperative_count': self.cooperative_count,
            'duration': int(time.time() - self.start_time) if self.start_time else 0,
            'intruder_name': self.intruder_claimed_name,
            'history': self.conversation_history
        }
        return summary