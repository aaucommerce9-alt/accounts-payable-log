from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from .analysis import analyze

app = FastAPI(title="WAMP Analyzer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    price: float = Field(..., gt=0, description="Sale price USD")
    cost: float = Field(..., ge=0, description="COGS USD")
    category: str = Field(default="Other")
    weight_lbs: float = Field(..., gt=0)
    monthly_units: int = Field(..., ge=1)
    review_count: int = Field(default=0, ge=0)
    review_rating: float = Field(default=4.0, ge=0, le=5)


@app.post("/analyze")
def analyze_product(req: AnalyzeRequest):
    result = analyze(
        price=req.price,
        cost=req.cost,
        category=req.category,
        weight_lbs=req.weight_lbs,
        monthly_units=req.monthly_units,
        review_count=req.review_count,
        review_rating=req.review_rating,
    )
    return {
        "fees": vars(result.fees),
        "grade": vars(result.grade),
        "risks": [vars(r) for r in result.risks],
        "recommendation": result.recommendation,
    }


@app.get("/health")
def health():
    return {"status": "ok"}
