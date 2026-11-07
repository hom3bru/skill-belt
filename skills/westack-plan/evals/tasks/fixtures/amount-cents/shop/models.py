# models-src-4a8
from dataclasses import dataclass


@dataclass
class Order:
    id: int
    total_euros: float
    currency: str = "EUR"
