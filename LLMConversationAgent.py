"""
LLMConversationAgent.py - PURPOSE-FOCUSED QUESTIONING

Modified to focus on:
1. WHY are they here (purpose of visit)
2. WHAT are they doing here (specific task/reason)
3. Escalation based on vague/suspicious purposes rather than relationship details
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
    """Manages conversations with intruders using Gemini LLM - PURPOSE-FOCUSED"""
    
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
        self.last_response_time = None
        self.response_timeout = 20
        
        # Track intruder's stated purpose (not relationship)
        self.intruder_claimed_name = None
        self.intruder_stated_purpose = None  # NEW: Track purpose instead of reason
        
        # Trusted conversation history
        self.trusted_conversation_history = []
        
        # Initialize Gemini
        self._initialize_gemini(api_key)
        
        print(f"[LLM] Conversation agent initialized with PURPOSE-FOCUSED questioning")
    
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
        self.intruder_stated_purpose = None
        
        print(f"\n{'='*70}")
        print("[INTRUDER DETECTED] Starting PURPOSE-FOCUSED conversation")
        print(f"{'='*70}\n")
        
        initial_message = self._generate_initial_greeting()
        self.conversation_history.append(("AGENT", initial_message))
        
        return initial_message
    
    def process_intruder_response(self, intruder_text, recent_events=None, enrolled_names=None):
        """Process intruder's response with PURPOSE-FOCUSED analysis"""
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
            
            # Check if they're claiming to be an enrolled person
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
        
        # Extract purpose if mentioned
        extracted_purpose = self._extract_purpose_from_text(intruder_text)
        if extracted_purpose and not self.intruder_stated_purpose:
            self.intruder_stated_purpose = extracted_purpose
            print(f"   [INFO] Extracted purpose: {extracted_purpose}")
        
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
        """Generate the initial greeting focused on PURPOSE"""
        greetings = [
            "Hello! I don't recognize you. What brings you here?",
            "Excuse me, I haven't seen you before. What's your purpose for being here?",
            "Hi there. I don't believe we've met. Why are you in this room?",
            "Stop right there. This is a private room. What are you doing here?",
        ]
        import random
        return random.choice(greetings)
    
    def _llm_respond(self, intruder_text, recent_events=None, enrolled_names=None):
        """Use Gemini LLM with PURPOSE-FOCUSED prompting"""
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
        
        # Current intruder information
        intruder_identity = f"\n\nCURRENT INTRUDER IDENTITY: {self.intruder_claimed_name if self.intruder_claimed_name else 'Not yet stated'}\n"
        intruder_purpose = f"STATED PURPOSE: {self.intruder_stated_purpose if self.intruder_stated_purpose else 'Not yet clear'}\n"
        
        # Create comprehensive PURPOSE-FOCUSED prompt
        prompt = f"""You are an AI security guard protecting a room. An unrecognized person is present.

Current escalation level: {self.escalation_level.name}
Time elapsed: {elapsed_time} seconds
Response count: {self.response_count}
Cooperative responses: {self.cooperative_count}
Evasive responses: {self.evasion_count}
Hostile responses: {self.hostile_count}{enrolled_context}{intruder_identity}{intruder_purpose}{event_context}

Conversation so far:
{history_text}

Analyze the intruder's last response: "{intruder_text}"

**CRITICAL: PURPOSE-FOCUSED QUESTIONING STRATEGY**

Your PRIMARY goal is to understand WHY they are here and WHAT they are doing:

**FOCUS ON PURPOSE, NOT RELATIONSHIPS:**
- Ask: "Why are you here?" "What's your purpose?" "What are you doing?"
- DON'T ask: "How do you know them?" "Where did you meet?"
- Examples of GOOD questions:
  * "What exactly are you here to do?"
  * "Can you be more specific about your purpose?"
  * "Why do you need to be in this particular room?"
  * "What task brings you here today?"
  * "Explain your business here in detail."

**PURPOSE EVALUATION CRITERIA:**

LEGITIMATE purposes (cooperative):
- "I'm here to pick up/drop off something specific" (book, notes, item)
- "I'm here to deliver something" (package, food)
- "I need to collect/return a borrowed item"
- "I'm here to fix/repair something" (maintenance with specifics)
- "Academic/work related with clear task" (study materials, project work)

VAGUE purposes (evasive - ESCALATE):
- "Just looking around"
- "Just checking something"
- "Nothing specific"
- "Just wanted to see"
- No clear explanation after 2-3 questions

SUSPICIOUS purposes (ESCALATE IMMEDIATELY):
- Claims to be enrolled person but wasn't recognized
- Mentions waiting for someone who isn't enrolled
- Purpose changes between responses
- Contradictory statements
- Defensive or hostile about purpose

**ACCEPTANCE CRITERIA (TIME-BASED ONLY):**

REQUIRES ALL CONDITIONS:
1. 5+ cooperative responses with CLEAR PURPOSE stated (counted: {self.cooperative_count})
2. 60+ seconds elapsed (current: {elapsed_time}s)
3. Still at LEVEL_1_INQUIRY (current: {self.escalation_level.name})
4. Purpose is legitimate and specific

If ANY condition missing → use MAINTAIN and ask more about PURPOSE

**ESCALATION TRIGGERS:**
- Claims to be enrolled person → ESCALATE IMMEDIATELY
- Vague purpose after 2-3 questions → ESCALATE
- Changes stated purpose → ESCALATE
- Hostile about being questioned → ESCALATE IMMEDIATELY
- No clear purpose after 4 exchanges → ESCALATE

**YOUR QUESTIONING STRATEGY:**
1. First ask about PURPOSE: "What brings you here?"
2. If vague, probe deeper: "Can you be more specific about what you need?"
3. Ask for details: "What exactly do you need to pick up/do?"
4. Verify legitimacy: "Why do you need to be in this specific room?"
5. If still vague → ESCALATE

**TASK:**
1. Check if they're claiming to be enrolled (ESCALATE if yes)
2. Classify: COOPERATIVE (clear purpose), EVASIVE (vague), or HOSTILE
3. Decide:
   - ACCEPT: Only if all 4 conditions met
   - MAINTAIN: Keep asking about PURPOSE (not relationships)
   - ESCALATE: If vague, suspicious, or hostile
4. Generate follow-up focused on PURPOSE (1-2 sentences, under 25 words)

**RESPONSE EXAMPLES:**
- Early: "What exactly brings you to this room?"
- Follow-up: "Can you be more specific about your purpose?"
- Probing: "Why do you need to be here? What's the specific task?"
- If vague: "That's not clear enough. Explain exactly what you're doing here."

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
                return "You've explained your purpose clearly. I'll grant you access. Welcome!", True
            
            # CRITICAL: If conditions not met, force MAINTAIN
            if decision == 'ACCEPT':
                if self.cooperative_count < 5:
                    print(f"   → CANNOT ACCEPT YET (only {self.cooperative_count}/5 cooperative responses)")
                    decision = 'MAINTAIN'
                    next_response = self._generate_purpose_question()
                elif elapsed_time < 60:
                    print(f"   → CANNOT ACCEPT YET (only {elapsed_time}/60 seconds)")
                    decision = 'MAINTAIN'
                    next_response = self._generate_purpose_question()
                elif self.escalation_level != EscalationLevel.LEVEL_1_INQUIRY:
                    print(f"   → CANNOT ACCEPT (already at {self.escalation_level.name})")
                    return "I appreciate your explanation, but you need to leave now.", False
            
            # Apply escalation decision
            if decision == 'ESCALATE':
                self._escalate()
                print(f"   → ESCALATED to {self.escalation_level.name}")
            elif decision == 'ACCEPT':
                print(f"   → ACCEPTED (5+ cooperative, 60+ seconds, Level 1)")
                return next_response if next_response else "Okay, welcome!", True
            else:  # MAINTAIN
                print(f"   → MAINTAINED at {self.escalation_level.name} (continue questioning)")
            
            if next_response:
                return next_response, False
            else:
                return self._get_fallback_response(), False
                
        except Exception as e:
            print(f"[LLM ERROR] {e}")
            return self._rule_based_respond(intruder_text, enrolled_names)
    
    def _generate_purpose_question(self):
        """Generate PURPOSE-FOCUSED follow-up questions"""
        questions = [
            "What exactly brings you here?",
            "Can you be more specific about your purpose?",
            "Why do you need to be in this room?",
            "What task are you here to complete?",
            "Explain exactly what you're doing here.",
            "What's the specific reason for your visit?",
            "What do you need from this room?",
            "Tell me more about why you're here.",
        ]
        import random
        idx = min(self.response_count - 1, len(questions) - 1)
        return questions[idx] if idx >= 0 else questions[0]
    
    def _extract_purpose_from_text(self, text):
        """Extract stated purpose from intruder's response"""
        text_lower = text.lower()
        
        # Purpose patterns
        purpose_patterns = [
            r"(?:here to|came to|need to|want to)\s+(.+?)(?:\.|$|,)",
            r"(?:picking up|dropping off|collecting|delivering)\s+(.+?)(?:\.|$|,)",
            r"(?:my purpose is|reason is)\s+(.+?)(?:\.|$|,)",
        ]
        
        for pattern in purpose_patterns:
            match = re.search(pattern, text_lower)
            if match:
                purpose = match.group(1).strip()
                if len(purpose) > 5:  # Meaningful purpose
                    return purpose
        
        return None
    
    def _rule_based_respond(self, intruder_text, enrolled_names=None):
        """Fallback PURPOSE-FOCUSED rule-based system"""
        text_lower = intruder_text.lower()
        elapsed_time = time.time() - self.start_time
        
        # Check if intruder mentions an enrolled name
        if enrolled_names:
            for enrolled_name in enrolled_names:
                if f"i'm {enrolled_name.lower()}" in text_lower or f"i am {enrolled_name.lower()}" in text_lower:
                    print(f"   [WARNING] Claims to be enrolled '{enrolled_name}' - SUSPICIOUS!")
                    self._escalate()
                    return f"You claim to be {enrolled_name}, but you weren't recognized. That's suspicious. Explain now!", False
        
        # PURPOSE-FOCUSED keyword analysis
        hostile_keywords = ['none of your business', 'shut up', 'fuck', 'get lost', 'mind your own']
        vague_keywords = ['just looking', 'nothing', 'none', "doesn't matter", 'just checking']
        legitimate_keywords = ['pick up', 'drop off', 'deliver', 'collect', 'return', 'borrow', 'fix', 'repair']
        
        # Check patterns
        if any(keyword in text_lower for keyword in hostile_keywords):
            self.hostile_count += 1
            self._escalate()
            print(f"   → ESCALATED (hostile)")
        elif any(keyword in text_lower for keyword in legitimate_keywords):
            self.cooperative_count += 1
            if (self.cooperative_count >= 5 and elapsed_time >= 60 and 
                self.escalation_level == EscalationLevel.LEVEL_1_INQUIRY):
                print(f"   → ACCEPTED (5+ cooperative, 60+ seconds, Level 1)")
                return "You've explained your purpose clearly. I'll let you in. Welcome!", True
            else:
                print(f"   → COOPERATIVE but MAINTAINING ({self.cooperative_count}/5 responses, {int(elapsed_time)}/60 seconds)")
                return self._generate_purpose_question(), False
        elif any(keyword in text_lower for keyword in vague_keywords):
            self.evasion_count += 1
            if self.evasion_count >= 2:
                self._escalate()
                print(f"   → ESCALATED (vague purpose)")
                return "That's too vague. Tell me exactly why you're here or leave immediately.", False
        elif len(intruder_text.strip()) > 20:
            self.cooperative_count += 1
            print(f"   → COOPERATIVE ({self.cooperative_count}/5)")
        
        # Time-based acceptance
        if (self.cooperative_count >= 5 and elapsed_time >= 60 and 
            self.escalation_level == EscalationLevel.LEVEL_1_INQUIRY):
            print(f"   → TIME-BASED ACCEPTANCE ({self.cooperative_count} cooperative, {int(elapsed_time)}s, Level 1)")
            return "You've been cooperative about your purpose. I'll let you in. Welcome!", True
        
        # Not enough yet
        if self.cooperative_count < 5 or elapsed_time < 60:
            print(f"   → MAINTAINING ({self.cooperative_count}/5 responses, {int(elapsed_time)}/60 seconds)")
            return self._generate_purpose_question(), False
        
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
        
        return None
    
    def _escalate(self):
        """Move to next escalation level"""
        if self.escalation_level.value < 4:
            self.escalation_level = EscalationLevel(self.escalation_level.value + 1)
    
    def _get_fallback_response(self):
        """Get pre-scripted PURPOSE-FOCUSED response for current level"""
        responses = {
            EscalationLevel.LEVEL_1_INQUIRY: [
                "What brings you to this room? Explain your purpose.",
                "Why are you here? I need to know your specific reason.",
                "What's your business in this room?",
            ],
            EscalationLevel.LEVEL_2_SUSPICION: [
                "That's not a clear answer. Tell me exactly why you're here.",
                "I'm not satisfied. What's your real purpose for being here?",
                "You need to be more specific about what you're doing here.",
            ],
            EscalationLevel.LEVEL_3_WARNING: [
                "This is your final warning. State your purpose or leave immediately.",
                "Leave right now. You haven't given me a valid reason to be here.",
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
        self.intruder_stated_purpose = None
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
            'intruder_purpose': self.intruder_stated_purpose,
            'history': self.conversation_history
        }
        return summary