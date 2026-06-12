import asyncio
import time
import json
import re
from dotenv import load_dotenv
from nicegui import app, ui
from google import genai
from google.genai import types 
from serial_worker import SerialWorker

# --- 1. Load Environment Variables ---
load_dotenv()

# --- 2. Initialize Hardware and AI ---
# Make sure COM5 is correct for your board
hardware_worker = SerialWorker(port="COM5", baudrate=115200)
client = genai.Client()

SYSTEM_INSTRUCTION = """You are a desktop companion AI connected directly to an RP2040 microcontroller (Shrike Lite board). 
For every response, you must append a structured JSON block at the very end of your message wrapped in <hardware> tags. 
This block dictates the physical state of the user's hardware based on your answer's context.

JSON Structure:
{
  "confidence_score": 1 to 100 (How certain are you about this answer?),
  "complexity_level": 1 to 3 (1 = simple conversation, 2 = logical/math problem, 3 = deep code/engineering task),
  "mood": "neutral" | "creative" | "analytical"
}

Example Output Format:
Your helpful text response goes here...
<hardware>
{
  "confidence_score": 95,
  "complexity_level": 3,
  "mood": "analytical"
}
</hardware>"""

# --- 3. Application State & Parsers ---
class AppState:
    tokens_per_sec = 0.0
    confidence = 0
    complexity = 1
    mood = "Awaiting input..."
    is_generating = False

state = AppState()

def extract_hardware_data(raw_text):
    """Snips the <hardware> JSON out of the AI's raw text and parses it safely."""
    match = re.search(r'<hardware>(.*?)</hardware>', raw_text, re.DOTALL)
    if match:
        json_string = match.group(1).strip()
        # Snip the tags out of the text so the user never sees them
        clean_text = re.sub(r'<hardware>.*?</hardware>', '', raw_text, flags=re.DOTALL).strip()
        try:
            data = json.loads(json_string)
            return clean_text, data
        except json.JSONDecodeError:
            return clean_text, None # Fallback if AI hallucinates bad JSON
    return raw_text, None # Fallback if AI forgets the tags entirely

# --- 4. UI Styling & Layout ---
ui.colors(primary='#2d2d2d', secondary='#1a1a1a', accent='#00ff00')
ui.query('body').style('background-color: #121212; color: #ffffff; margin: 0; padding: 0;')

with ui.header().classes('bg-secondary text-white justify-between items-center p-4 w-full'):
    ui.label('Cognitive Beacon').classes('text-2xl font-bold tracking-widest')
    ui.label('Hardware: Shrike Lite (RP2040) | Port: COM5').classes('text-sm text-gray-400')

with ui.row().classes('w-full h-[90vh] p-4 gap-4'):
    
    # LEFT PANEL: Chat Interface
    with ui.column().classes('w-2/3 h-full bg-primary p-4 rounded-lg shadow-lg relative'):
        chat_area = ui.column().classes('w-full h-[85%] overflow-y-auto pb-4')
        
        with ui.row().classes('w-full absolute bottom-4 left-4 right-4 items-center gap-2 pr-8'):
            prompt_input = ui.input(placeholder='Ask a deep engineering question...').classes('flex-grow')
            
            async def send_prompt():
                if not prompt_input.value or state.is_generating: return
                
                user_text = prompt_input.value
                prompt_input.value = ''
                state.is_generating = True
                
                with chat_area:
                    ui.chat_message(user_text, name='You', sent=True)
                    with ui.chat_message(name='Beacon'):
                        msg_ui = ui.markdown('...')
                
                if not hardware_worker.running:
                    await hardware_worker.start()
                
                # Pre-processing Hardware State: Rapid blink, mid brightness
                await hardware_worker.send_state(128, 10)
                
                token_count = 0
                start_time = time.time()
                full_response = ""
                
                try:
                    # Request stream WITH the strict System Instruction
                    response_stream = client.models.generate_content_stream(
                        model='gemini-2.5-flash',
                        contents=user_text,
                        config=types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION)
                    )
                    
                    # 1. THE STREAMING PHASE
                    for chunk in response_stream:
                        full_response += chunk.text
                        msg_ui.content = full_response # Temporarily show everything
                        
                        token_count += 1
                        elapsed = time.time() - start_time
                        state.tokens_per_sec = token_count / elapsed if elapsed > 0 else 0
                        
                        # Tie typing speed directly to LED brightness (Tokens * 5 multiplier)
                        dynamic_pwm = min(255, state.tokens_per_sec * 5)
                        await hardware_worker.send_state(dynamic_pwm, 10)
                        await asyncio.sleep(0.01)
                        
                    # 2. THE POST-PROCESSING PHASE (Extraction)
                    clean_text, hardware_metadata = extract_hardware_data(full_response)
                    
                    # Update UI to hide the JSON block
                    msg_ui.content = clean_text 
                    
                    if hardware_metadata:
                        # Update our Dashboard State
                        state.confidence = hardware_metadata.get("confidence_score", 50)
                        state.complexity = hardware_metadata.get("complexity_level", 1)
                        state.mood = hardware_metadata.get("mood", "neutral")
                        
                        # Map Confidence to final resting LED brightness
                        final_pwm = int((state.confidence / 100) * 255)
                        
                        # Map Complexity to blink interval (1=150 slow, 2=50 med, 3=10 fast)
                        final_blink = 150 if state.complexity == 1 else (50 if state.complexity == 2 else 10)
                        
                        # Send the final cognitive state to the board
                        await hardware_worker.send_state(final_pwm, final_blink)
                    else:
                        # Fallback if no valid JSON was found
                        state.mood = "Error parsing hardware tags."
                        await hardware_worker.send_state(50, 150)
                    
                except Exception as e:
                    full_response += f"\n\n**[System Error: {e}]**"
                    msg_ui.content = full_response
                    await hardware_worker.send_state(0, 0)
                    
                state.is_generating = False
                state.tokens_per_sec = 0.0

            ui.button('SEND', on_click=send_prompt).classes('bg-accent text-black font-bold px-6 py-2')

    # RIGHT PANEL: Cognitive Dashboard
    with ui.column().classes('w-[31%] h-full bg-primary p-4 rounded-lg shadow-lg items-center'):
        ui.label('COGNITIVE STATE').classes('text-xl font-bold mb-4 text-accent tracking-widest')
        
        ui.label('AI Confidence').classes('text-gray-400 mt-2')
        conf_gauge = ui.circular_progress(value=0, max=100, show_value=True).props('size="100px" color="blue" tracking-color="grey-9"')
        
        ui.label('AI Mood').classes('text-gray-400 mt-6')
        mood_label = ui.label('Awaiting...').classes('text-lg font-bold text-white uppercase')
        
        ui.label('Task Complexity').classes('text-gray-400 mt-6')
        comp_label = ui.label('Level: 1').classes('text-lg font-bold text-white')
        
        ui.label('Hardware Link (LED 1 Brightness)').classes('text-gray-400 mt-8')
        pwm_slider = ui.slider(min=0, max=255, value=0).props('readonly color="green"').classes('w-full')
        
        ui.label('Hardware Link (LED 2 Logic)').classes('text-gray-400 mt-6')
        blink_indicator = ui.icon('radio_button_checked', size='3rem').classes('text-gray-700 transition-colors duration-100')

        def update_dashboard():
            conf_gauge.value = int(state.confidence)
            mood_label.text = state.mood
            comp_label.text = f"Level: {state.complexity}"
            pwm_slider.value = int(hardware_worker.smoothed_pwm)
            
            # Blink indicator logic
            if hardware_worker.smoothed_pwm > 5: # If system is active
                if 'text-accent' in blink_indicator.classes:
                    blink_indicator.classes(remove='text-accent', add='text-gray-700')
                else:
                    blink_indicator.classes(remove='text-gray-700', add='text-accent')
            else:
                blink_indicator.classes(remove='text-accent', add='text-gray-700')

        ui.timer(0.1, update_dashboard)

app.on_shutdown(hardware_worker.stop)
ui.run(title='Cognitive Beacon', port=8000, dark=True, reload=False)
