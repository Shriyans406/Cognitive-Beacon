import os
import time
import asyncio
from fastapi import FastAPI, BackgroundTasks
from google import genai
from serial_worker import SerialWorker

app = FastAPI()

# Initialize our Serial Worker on COM5
hardware_worker = SerialWorker(port="COM5", baudrate=115200)

# Initialize Gemini Client
# Make sure you ran 'set GEMINI_API_KEY=your_key' or 'export GEMINI_API_KEY=your_key' in your terminal
client = genai.Client()

@app.on_event("startup")
async def startup_event():
    """Triggers automatically when the server starts up."""
    await hardware_worker.start()

@app.on_event("shutdown")
async def shutdown_event():
    """Triggers automatically when you stop the server (Ctrl+C)."""
    await hardware_worker.stop()

@app.get("/ask")
async def ask_gemini(prompt: str):
    """
    Endpoint to send a prompt to Gemini. 
    Usage: http://127.0.0.1:8000/ask?prompt=Your+Question
    """
    print(f"\n[User Prompt]: {prompt}")
    print("[Gemini Stream Response]: ", end="", flush=True)

    token_count = 0
    start_time = time.time()

    try:
        # Call the live streaming API
        response_stream = client.models.generate_content_stream(
            model='gemini-2.5-flash',
            contents=prompt,
        )

        for chunk in response_stream:
            text_chunk = chunk.text
            print(text_chunk, end="", flush=True)
            
            # Count the tokens/words generated in this burst
            token_count += 1
            elapsed = time.time() - start_time
            
            # Avoid division by zero, calculate current generation speed
            if elapsed > 0:
                tokens_per_second = token_count / elapsed
            else:
                tokens_per_second = 0

            # Mock metrics mapping: 
            # If prompt length is high, let's increase blink complexity indicators
            blink_rate_code = 20 if len(prompt) > 30 else 80 

            # Push these metrics straight into our background hardware queue
            await hardware_worker.send_metrics(tokens_per_second, blink_rate_code)
            
            # Yield control back to the async loop briefly so the background worker can run
            await asyncio.sleep(0.01)

        print("\n[Stream Complete]")
        
        # After stream finishes, return the board to a dim passive state
        await hardware_worker.send_metrics(5.0, 150)
        return {"status": "success", "total_tokens_processed": token_count}

    except Exception as e:
        print(f"\n[Gemini Error] Failed during stream: {e}")
        return {"status": "error", "message": str(e)}