from dotenv import load_dotenv
import os
import base64
from email.mime.text import MIMEText

from openai import OpenAI
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# -------------------------
# CONFIG
# -------------------------
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
LABEL_NAME = "AI_TEST"
MODEL_ID = "openai/gpt-oss-20b:groq"

# -------------------------
# Load env
# -------------------------
load_dotenv()
hf_token = os.getenv("HF_TOKEN")

if not hf_token:
    raise ValueError("HF_TOKEN not found in .env")

# -------------------------
# HF Client
# -------------------------
client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=hf_token,
)

# -------------------------
# Gmail Auth
# -------------------------
def gmail_auth():
    flow = InstalledAppFlow.from_client_secrets_file(
        r"D:\Najma\Gmail_try\credentials.json",
        SCOPES
    )
    creds = flow.run_local_server(port=0)
    return build("gmail", "v1", credentials=creds)

# -------------------------
# Get Label ID
# -------------------------
def get_label_id(service, name):
    labels = service.users().labels().list(userId="me").execute()
    for label in labels["labels"]:
        if label["name"] == name:
            return label["id"]
    return None

# -------------------------
# Fetch unread emails
# -------------------------
def get_unread_messages(service, label_id):
    res = service.users().messages().list(
        userId="me",
        labelIds=[label_id, "UNREAD"],
        maxResults=5
    ).execute()
    return res.get("messages", [])

# -------------------------
# Extract email body
# -------------------------
def extract_body(message):
    payload = message["payload"]

    if "parts" in payload:
        for part in payload["parts"]:
            if part["mimeType"] == "text/plain":
                data = part["body"]["data"]
                return base64.urlsafe_b64decode(data).decode("utf-8")

    return ""

# -------------------------
# Generate AI reply
# -------------------------
def generate_reply(email_text):
    response = client.chat.completions.create(
        model=MODEL_ID,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a professional IT Support Team assistant.\n"
                    "Write a polite, clear, and concise email reply.\n"
                    "Acknowledge the user's request without making promises or timelines.\n"
                    "Maintain a professional corporate tone.\n"
                    "Do not ask unnecessary questions.\n"
                    "Keep the response brief and helpful.\n\n"
                    "End the email exactly with:\n\n"
                    "Thanks & Regards,\n"
                    "IT Support Team"
                )
            },
            {
                "role": "user",
                "content": email_text
            }
        ],
        temperature=0.4,
        max_tokens=180
    )

    return response.choices[0].message.content.strip()

# -------------------------
# Send reply
# -------------------------
def send_reply(service, original, reply_text):
    headers = original["payload"]["headers"]

    sender = next(h["value"] for h in headers if h["name"] == "From")
    subject = next(h["value"] for h in headers if h["name"] == "Subject")

    msg = MIMEText(reply_text)
    msg["To"] = sender
    msg["Subject"] = "Re: " + subject

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    service.users().messages().send(
        userId="me",
        body={
            "raw": raw,
            "threadId": original["threadId"]
        }
    ).execute()

# -------------------------
# MAIN
# -------------------------
def main():
    service = gmail_auth()

    label_id = get_label_id(service, LABEL_NAME)
    if not label_id:
        print("Label AI_TEST not found")
        return

    messages = get_unread_messages(service, label_id)
    if not messages:
        print("No unread emails")
        return

    for m in messages:
        msg = service.users().messages().get(
            userId="me",
            id=m["id"],
            format="full"
        ).execute()

        body = extract_body(msg)
        if len(body) < 10:
            continue

        reply = generate_reply(body)
        send_reply(service, msg, reply)

        # Mark as read
        service.users().messages().modify(
            userId="me",
            id=m["id"],
            body={"removeLabelIds": ["UNREAD"]}
        ).execute()

        print("Replied successfully")

if __name__ == "__main__":
    main()
