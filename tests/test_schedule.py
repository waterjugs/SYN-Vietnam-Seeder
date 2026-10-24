import xml.etree.ElementTree as ET
from datetime import datetime

from seeder import schedule

NS = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}


def parse(xml: str) -> ET.Element:
    return ET.fromstring(xml.replace('encoding="UTF-16"', ""))


def test_starts_today_if_time_is_still_ahead():
    root = parse(schedule.task_xml("19:30", r"C:\x\SynSeeder.exe", "--seed", now=datetime(2026, 10, 24, 8, 0)))
    assert root.find(".//t:StartBoundary", NS).text == "2026-10-24T19:30:00"
    assert root.find(".//t:DaysInterval", NS).text == "1"


def test_starts_tomorrow_if_time_has_passed():
    root = parse(schedule.task_xml("07:00", "p", "--seed", now=datetime(2026, 10, 24, 8, 0)))
    assert root.find(".//t:StartBoundary", NS).text == "2026-10-25T07:00:00"


def test_runs_on_battery_late_and_once():
    root = parse(schedule.task_xml("07:00", "p", "--seed"))
    assert root.find(".//t:DisallowStartIfOnBatteries", NS).text == "false"
    assert root.find(".//t:StartWhenAvailable", NS).text == "true"
    assert root.find(".//t:MultipleInstancesPolicy", NS).text == "IgnoreNew"
    assert root.find(".//t:LogonType", NS).text == "InteractiveToken"


def test_command_is_escaped():
    root = parse(schedule.task_xml("07:00", r"C:\Users\A&B\SynSeeder.exe", "--seed"))
    assert root.find(".//t:Command", NS).text == r"C:\Users\A&B\SynSeeder.exe"
    assert root.find(".//t:Arguments", NS).text == "--seed"


def test_dev_command_uses_python_module():
    program, arguments = schedule.seed_command()
    assert arguments == "-m seeder --seed"
