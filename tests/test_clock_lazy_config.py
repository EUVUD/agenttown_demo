"""Importing the clock must not load configuration."""

from __future__ import annotations

from tests.support.fresh_interpreter import run_in_fresh_interpreter


def test_clock_parses_and_orders_times_without_loading_config() -> None:
    completed = run_in_fresh_interpreter(
        "import src.config as config\n"
        "from src.world.clock import Stage, TimeState\n"
        "early = TimeState.from_string('Y2020-W03-plan')\n"
        "late = TimeState.from_string('Y2020-W03-activity-D2')\n"
        "assert early < late and late.stage == Stage.ACTIVITY and late.day == 2\n"
        "assert str(early) == 'Y2020-W03-plan'\n"
        "assert config._CONFIG is None, 'importing the clock loaded config'\n"
        "print('LAZY OK')\n"
    )

    assert completed.returncode == 0 and "LAZY OK" in completed.stdout, (
        completed.stdout + completed.stderr
    )


def test_clock_reads_week_counts_from_config_when_needed() -> None:
    completed = run_in_fresh_interpreter(
        "from pathlib import Path\n"
        "import src.config as config\n"
        "root = Path(sys.path[0])\n"
        "config.load_config(root / 'config.example.json')\n"
        "from src.world.clock import Stage, TimeState\n"
        "weeks = config.get_config()['world']['time']['n_week']\n"
        "previous = TimeState(2021, 1, Stage.PLAN).minus_x_weeks(2)\n"
        "assert (previous.year, previous.week) == (2020, weeks), previous\n"
        "print('WEEKS OK')\n"
    )

    assert completed.returncode == 0 and "WEEKS OK" in completed.stdout, (
        completed.stdout + completed.stderr
    )
