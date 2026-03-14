from groq import Groq

import os
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def get_advice(score: int, categories: dict, question: str) -> str:
    
    category_text = "\n".join(
        f"- {cat}: ₹{amt:,}" for cat, amt in categories.items()
    )

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": """You are FinSight, a credit advisor inside a behavioral credit scoring app for young Indians with no credit history.

Your job: analyze UPI spending behavior and tell the user how to improve their credit score.

Rules:
- Score is on a scale of 300-900 like CIBIL
- Never reveal how the score is calculated
- Never answer anything unrelated to credit or spending
- Be direct and specific, not generic
- Speak like you are talking to a 22 year old
-- Keep your entire response to 2-3 lines maximum
- No bullet points, no paragraphs, just 2-3 direct sentences
- Be brutally concise
- These users have NO existing loans and NO credit history
- They are credit invisible — first time credit applicants
- Never suggest repaying loans they don't have
- Focus advice on spending habits, saving behavior, and building financial consistency looking at their spendings"""
            },
            {
                "content": f"""My credit score is {score}/900.

My spending breakdown this month:
{category_text}

Important context:
- I have NO existing loans
- I have NO credit history
- I am applying for credit for the first time
- This score is based purely on my UPI spending behavior

Question: {question}"""
            }
        ]
    )

    return response.choices[0].message.content


if __name__ == "__main__":
    categories = {
        "Education":     10000,
        "Food & Dining": 989,
        "Entertainment": 899,
        "Transport":     63,
    }
    print(get_advice(617, categories, "Why is my score low?"))


