from datetime import datetime, timedelta, timezone


class TimeUtilities:
    NANOS_PER_SECOND = 1_000_000_000
    NANOS_PER_TICK = 100
    TICKS_PER_MILLISECOND = 10_000
    TICKS_PER_SECOND = 10_000_000

    @staticmethod
    def get_now_since_midnight() -> timedelta:
        """Return a timedelta representing the current UTC time since midnight (UTC)."""
        now = datetime.now(timezone.utc)
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return now - midnight

    @staticmethod
    def get_now_since_midnight_in_seconds() -> float:
        return TimeUtilities.get_now_since_midnight().total_seconds()

    @staticmethod
    def interval_in_nanoseconds(frequency_hz: float) -> int:
        """Return the number of nanoseconds for the given frequency."""
        return int((1.0 / frequency_hz) * TimeUtilities.NANOS_PER_SECOND)


class NanoSeconds:
    def __init__(self, value: int):
        self.value = value

    @property
    def seconds(self) -> float:
        return self.value / float(TimeUtilities.NANOS_PER_SECOND)

    @property
    def ticks(self) -> int:
        return self.value // TimeUtilities.NANOS_PER_TICK

    def __add__(self, other: "NanoSeconds") -> "NanoSeconds":
        return NanoSeconds(self.value + other.value)

    def __sub__(self, other: "NanoSeconds") -> "NanoSeconds":
        return NanoSeconds(self.value - other.value)
