It contain two files.autoreply_hftoken and autoreply_opnai.
## autoreply_hftoken 
This file is for generating auto reply for gmail.reply are generated using free hugging face models.in which we used .env file to store our secret keys;HF_Token="...".Also we have credentials.json file for integrating gmail.

## autoreply_opnai
Here I experiment with outlook gmail reply generation using opnai keys with model gpt4mini,also created some labels to classify the gmails.
.env file contain
OPENAI_API_KEY,TENANT_ID,CLIENT_ID,CLIENT_SECRET,USER_EMAIL
