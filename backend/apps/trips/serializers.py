from dateutil import parser as date_parser
from rest_framework import serializers

MAX_PLACE_CHARS = 500
MAX_LOAD_LBS = 200_000
MIN_INTERVAL_MI = 1
MAX_INTERVAL_MI = 200
# Departure must fall inside the Open-Meteo fetch window (past + forecast)
# with tolerance for clock skew.
DEPARTURE_PAST_DAYS = 2
DEPARTURE_FUTURE_DAYS = 4


class TripPlanSerializer(serializers.Serializer):
    origin = serializers.CharField(
        max_length=MAX_PLACE_CHARS, allow_blank=False, trim_whitespace=True
    )
    destination = serializers.CharField(
        max_length=MAX_PLACE_CHARS, allow_blank=False, trim_whitespace=True
    )
    # ISO datetime; parsed with dateutil for tz tolerance.
    departure = serializers.CharField()
    load_lbs = serializers.FloatField(min_value=0, max_value=MAX_LOAD_LBS)
    interval_miles = serializers.FloatField(
        min_value=MIN_INTERVAL_MI, max_value=MAX_INTERVAL_MI, required=False
    )

    def validate_departure(self, value: str):
        from datetime import datetime, timedelta, timezone

        try:
            dt = date_parser.isoparse(value)
        except Exception as exc:
            raise serializers.ValidationError(f"Invalid ISO datetime: {value}") from exc
        if dt.tzinfo is None:
            raise serializers.ValidationError(
                "departure must include a timezone offset (e.g. +00:00 or Z)."
            )
        now = datetime.now(timezone.utc)
        earliest = now - timedelta(days=DEPARTURE_PAST_DAYS)
        latest = now + timedelta(days=DEPARTURE_FUTURE_DAYS)
        if not (earliest <= dt <= latest):
            raise serializers.ValidationError(
                f"departure must be within {DEPARTURE_PAST_DAYS}d past / "
                f"{DEPARTURE_FUTURE_DAYS}d future for the weather window."
            )
        return dt

    def validate(self, attrs):
        origin = (attrs.get("origin") or "").strip()
        dest = (attrs.get("destination") or "").strip()
        if origin and dest and origin.lower() == dest.lower():
            raise serializers.ValidationError("origin and destination must differ.")
        return attrs
