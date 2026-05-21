from flask import Flask, request, render_template
from openai import OpenAI, AuthenticationError, RateLimitError
import os

import os
from dotenv import load_dotenv

load_dotenv(
    "/Users/shivam13juna/Documents/scaler/iitr_classes/llm_ref/openai_key.env"
)  # reads .env file in the current directory


#flask --app hello.py run
#curl --location 'http://127.0.0.1:5000/'

import truststore

truststore.inject_into_ssl()


app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Shared conversation state (for demo only, reset on server restart)
messages = [
    {
        "role": "system",
        "content": "You are a friendly Python tutor who explains concepts clearly.",
    }
]


def safe_chat_call(messages):
    try:
        return client.chat.completions.create(model="gpt-4o-mini", messages=messages)
    except AuthenticationError:
        return None
    except RateLimitError:
        return None
    except Exception:
        return None


@app.route("/", methods=["GET", "POST"])
def index():
    reply = ""
    usage_info = ""
    if request.method == "POST":
        user_text = request.form["user_input"]
        messages.append({"role": "user", "content": user_text})

        resp = safe_chat_call(messages)
        if resp:
            reply = resp.choices[0].message.content
            messages.append({"role": "assistant", "content": reply})

            usage = resp.usage
            usage_info = f"Prompt: {usage.prompt_tokens}, Completion: {usage.completion_tokens}, Total: {usage.total_tokens}"

    return render_template("index.html", reply=reply, usage=usage_info)


# command to run flask app

# flask run --app flask_code.py --debug
