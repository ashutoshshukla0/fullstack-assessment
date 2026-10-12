"""Risk levels."""

from enum import IntEnum


class RiskLevel(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4

    @property
    def label(self) -> str:
        return {
            RiskLevel.LOW: "Low",
            RiskLevel.MODERATE: "Moderate",
            RiskLevel.HIGH: "High",
            RiskLevel.SEVERE: "Severe",
            RiskLevel.NO_TRAVEL: "No Travel",
        }[self]

    @classmethod
    def from_label(cls, label: str) -> "RiskLevel":
        for level in cls:
            if level.label.lower() == label.lower():
                return level
        raise ValueError(f"Unknown risk label: {label}")


RISK_COLORS = {
    RiskLevel.LOW: "#22c55e",
    RiskLevel.MODERATE: "#eab308",
    RiskLevel.HIGH: "#f97316",
    RiskLevel.SEVERE: "#ef4444",
    RiskLevel.NO_TRAVEL: "#7f1d1d",
}
