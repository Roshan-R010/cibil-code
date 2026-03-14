from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from advisor import get_advice
import tempfile
import os

from phonepe_parser import parse_phonepe_pdf
from categorizer import categorize_transaction
from scorer import calculate_score

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    # Save uploaded file to a temp location
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        contents = await file.read()
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        # Parse and categorize
        transactions = parse_phonepe_pdf(tmp_path)
        transactions = categorize_transaction(transactions)

        # Build category summary for charts
        categories = {}
        for t in transactions:
            if t['type'] == 'DEBIT':
                cat = t['category']
                categories[cat] = categories.get(cat, 0) + abs(t['amount'])

        return {
            "status":       "success",
            "transactions": transactions,
            "categories":   categories,
            "total_txns":   len(transactions),
        }

    except ValueError as e:
        return {"status": "error", "message": str(e)}

    finally:
        os.remove(tmp_path)


class PersonalDetails(BaseModel):
    name:               str
    age:                int
    occupation:         str
    employment_type:    str
    experience:         float
    monthly_income:     float
    housing_status:     str
    years_at_residence: float
    earning_members:    int
    loan_purpose:       str

class ScoreRequest(BaseModel):
    transactions:   list
    personal:       PersonalDetails

@app.post("/score")
async def score(request: ScoreRequest):
    try:
        result = calculate_score(
            request.transactions,
            request.personal.dict()
        )
        return {"status": "success", **result}
    except Exception as e:
        return {"status": "error", "message": str(e)}

class AdvisorRequest(BaseModel):
    score:      int
    categories: dict
    question:   str

@app.post("/advisor")
async def advisor(request: AdvisorRequest):
    try:
        advice = get_advice(request.score, request.categories, request.question)
        return {"status": "success", "advice": advice}
    except Exception as e:
        return {"status": "error", "message": str(e)}

    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)