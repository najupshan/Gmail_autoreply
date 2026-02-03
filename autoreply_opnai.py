import os
import requests
from dotenv import load_dotenv
from openai import OpenAI
import msal

# -------------------------
# Load environment variables
# -------------------------
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
USER_EMAIL = os.getenv("USER_EMAIL")

if not all([OPENAI_API_KEY, TENANT_ID, CLIENT_ID, CLIENT_SECRET, USER_EMAIL]):
    raise ValueError("One or more environment variables are missing!")

# -------------------------
# OpenAI Client (GPT-4 mini)
# -------------------------
client = OpenAI(api_key=OPENAI_API_KEY)

# -------------------------
# MSAL token function
# -------------------------
def get_access_token():
    app = msal.ConfidentialClientApplication(
        client_id=CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
        client_credential=CLIENT_SECRET,
    )
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    if "access_token" in result:
        return result["access_token"]
    else:
        raise Exception("Failed to get access token: " + str(result))

# -------------------------
# Fetch unread emails
# -------------------------
def get_unread_emails(token):
    url = f"https://graph.microsoft.com/v1.0/users/{USER_EMAIL}/mailFolders/Inbox/messages"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"$filter": "isRead eq false", "$top": 10}  # adjust batch size
    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()
    return resp.json().get("value", [])

# -------------------------
# Get folder IDs
# -------------------------
def get_mail_folders(token):
    url = f"https://graph.microsoft.com/v1.0/users/{USER_EMAIL}/mailFolders"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    folders = resp.json().get("value", [])
    return {f["displayName"]: f["id"] for f in folders}

# -------------------------
# Classify email to folder
# -------------------------
def classify_email(email_text, folders):
    text = email_text.lower()
    if "setup" in text or "project" in text:
        return folders.get("Project setup")
    elif "access" in text or "login" in text:
        return folders.get("Acecess")
    else:
        return folders.get("General")

# -------------------------
# Move email to folder
# -------------------------
def move_email(token, message_id, folder_id):
    url = f"https://graph.microsoft.com/v1.0/users/{USER_EMAIL}/messages/{message_id}/move"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"destinationId": folder_id}
    resp = requests.post(url, headers=headers, json=payload)
    resp.raise_for_status()
    return resp.json()  # returns new message info

# -------------------------
# Generate AI reply
# -------------------------
def generate_reply(email_text):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a professional IT Support Team assistant.\n"
                    "Write a polite, clear, and concise email reply.\n"
                    "Acknowledge the user's request without committing to timelines.\n"
                    "Maintain a professional corporate tone.\n"
                    "Do not ask unnecessary questions.\n\n"
                    "End the email exactly with:\n\n"
                    "Thanks & Regards,\n"
                    "IT Support Team"
                )
            },
            {"role": "user", "content": email_text}
        ],
        temperature=0.4,
        max_tokens=180
    )
    return response.choices[0].message.content.strip()

# -------------------------
# Send reply
# -------------------------
def send_reply(token, message, reply_text):
    url = f"https://graph.microsoft.com/v1.0/users/{USER_EMAIL}/sendMail"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "message": {
            "subject": "Re: " + message.get("subject", "(No Subject)"),
            "body": {"contentType": "Text", "content": reply_text},
            "toRecipients": [
                {"emailAddress": {"address": message["from"]["emailAddress"]["address"]}}
            ]
        }
    }
    resp = requests.post(url, headers=headers, json=payload)
    resp.raise_for_status()

# -------------------------
# MAIN
# -------------------------
def main():
    token = get_access_token()
    unread_emails = get_unread_emails(token)
    folders = get_mail_folders(token)

    if not unread_emails:
        print("No unread emails.")
        return

    for msg in unread_emails:
        body_text = msg.get("body", {}).get("content", "").strip()
        if len(body_text) < 5:
            continue

        # 1️⃣ Generate reply
        reply = generate_reply(body_text)
        send_reply(token, msg, reply)

        # 2️⃣ Classify folder
        folder_id = classify_email(body_text, folders)

        # 3️⃣ Move email to folder (keep unread)
        move_email(token, msg["id"], folder_id)

        print(f"Replied and moved email from {msg['from']['emailAddress']['address']} to folder ID {folder_id}")

if __name__ == "__main__":
    main()
