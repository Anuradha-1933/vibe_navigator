import openai
import os
import json # Import json to handle the AI's output

# --- Configuration ---
# Make sure your OPENAI_API_KEY is set as an environment variable
# This line will read it automatically.
openai.api_key = os.getenv("OPENAI_API_KEY")

# --- We changed this to an 'async def' function ---
# This allows our FastAPI server to call OpenAI without freezing.
async def summarize_reviews(reviews: list[str]) -> str:
    """
    Summarizes a list of reviews to create a 'vibe' with emojis and tags.
    This is an asynchronous function.
    """
    # Check if we have an API key before making a call
    if not openai.api_key:
        print("ERROR: OPENAI_API_KEY environment variable not set.")
        # We will return a structured error message as a JSON string
        error_message = {
            "summary": "AI Summarizer is not configured. Missing API Key.",
            "mood_tags": ["error"],
            "key_themes": ["configuration"]
        }
        return json.dumps(error_message)

    # Combine the reviews into a single text block for the prompt
    reviews_text = "\n- ".join(reviews)

    # A good prompt is key! We will ask for a JSON output.
    # This is much more reliable than trying to parse plain text.
    prompt = f"""
    Based on the following user reviews, analyze the overall vibe of the place.
    Provide a summary that includes a short description, mood tags, and key themes.

    Reviews:
    - {reviews_text}

    Please provide your response as a JSON object with the following keys: "summary", "mood_tags", "key_themes".
    - The "summary" should be a short, catchy description with 1-3 emojis.
    - The "mood_tags" should be a list of 3-5 relevant string tags (e.g., "cozy", "lively", "quiet").
    - The "key_themes" should be a list of 3-5 relevant string themes (e.g., "good for dates", "great coffee", "noisy").
    """

    try:
        # --- CORRECTED ASYNCHRONOUS API CALL ---
        # This uses the syntax for the older openai==0.27.8 library
        # and 'acreate' for an async call.
        response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that analyzes customer reviews and summarizes the vibe of a place into a JSON format."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=250
        )
        # We return the content directly, which should be our JSON string.
        return response.choices[0].message['content']

    except Exception as e:
        print(f"An error occurred with the OpenAI API: {e}")
        # Return a structured error so the main app doesn't crash
        error_message = {
            "summary": f"An error occurred while generating the AI summary: {e}",
            "mood_tags": ["error"],
            "key_themes": ["api_failure"]
        }
        return json.dumps(error_message)

# The __main__ block is for testing this file alone.
# Because our function is now async, we need to use asyncio to run it.
if __name__ == '__main__':
    import asyncio

    # Example reviews for testing
    test_reviews = [
        "This place is so cozy and warm, perfect for a rainy day with a book. The coffee was amazing.",
        "A bit too crowded for my taste, and very loud. But I have to admit the decor was very trendy and aesthetic.",
        "Loved the vibe! It's super lively and the staff is incredibly friendly. Great spot to meet with friends.",
        "The music was fantastic and the lighting creates a really cool atmosphere. Will be back for sure."
    ]

    async def run_test():
        print("--- Testing AI Vibe Summary ---")
        # Make sure you have set your OPENAI_API_KEY!
        if not os.getenv("OPENAI_API_KEY"):
            print("\n!!! WARNING: OPENAI_API_KEY is not set. !!!")
            print("You need to set it in your terminal for this test to work.")
            print("For example (on Mac/Linux): export OPENAI_API_KEY='your_key_here'")
            return

        summary_json = await summarize_reviews(test_reviews)
        print("\nRaw JSON from AI:")
        print(summary_json)

        print("\nParsed Summary:")
        try:
            summary_data = json.loads(summary_json)
            print(f"Vibe: {summary_data.get('summary')}")
            print(f"Mood Tags: {summary_data.get('mood_tags')}")
            print(f"Key Themes: {summary_data.get('key_themes')}")
        except json.JSONDecodeError:
            print("Could not parse the JSON response from the AI.")


    # Run the async test function
    asyncio.run(run_test())