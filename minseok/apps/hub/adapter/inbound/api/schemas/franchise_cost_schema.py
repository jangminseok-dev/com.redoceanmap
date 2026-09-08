from pydantic import BaseModel


class FranchiseCostItemSchema(BaseModel):
    year: int
    sector: str
    industryName: str
    franchiseFee: int = 0
    educationFee: int = 0
    deposit: int = 0
    otherFee: int = 0
    totalAmount: int
    brandCount: int | None = None
    raw: dict | None = None


class FranchiseCostIngestRequest(BaseModel):
    items: list[FranchiseCostItemSchema]


class FranchiseCostIngestResult(BaseModel):
    received: int
    saved: int
