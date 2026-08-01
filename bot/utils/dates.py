from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


def now_local(tz_name: str) -> datetime:
    return datetime.now(ZoneInfo(tz_name))


def today_str(tz_name: str) -> str:
    return now_local(tz_name).date().isoformat()


def date_days_ago(tz_name: str, days: int) -> str:
    return (now_local(tz_name).date() - timedelta(days=days)).isoformat()


def week_start_str(tz_name: str) -> str:
    d = now_local(tz_name).date()
    return (d - timedelta(days=d.weekday())).isoformat()


def days_between(date_from: str, date_to: str) -> int:
    return (date.fromisoformat(date_to) - date.fromisoformat(date_from)).days
