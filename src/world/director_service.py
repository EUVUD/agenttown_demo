from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from src.world.director import create_director_event, resolve_director_events
from src.world.template_world import add_character_to_world, create_world_from_template
from src.world.templates import TemplateRegistry
from src.world.visualization import generate_visualization_snapshot


def _active_world_time(active_world: Any | None) -> str | None:
    """Return the active world's current time label, or None without a clock."""
    get_time = getattr(getattr(active_world, "clock", None), "get_time", None)
    return str(get_time()) if callable(get_time) else None


class DirectorWorldService:
    """Small opt-in backend facade for template-driven director worlds.

    Every method that refreshes the visualization snapshot accepts an optional
    ``time`` label. When it is omitted the snapshot time is inferred from the run
    data, so each safe point gets its own snapshot file.
    """

    def __init__(
        self,
        *,
        data_root: str | Path = "data",
        templates_root: str | Path = "data/world_templates",
    ) -> None:
        self.data_root = Path(data_root)
        self.templates_root = Path(templates_root)
        self.registry = TemplateRegistry(root=self.templates_root)

    def get_template_schema(self, template_id: str) -> dict:
        return self.registry.get_creator_schema(template_id)

    def create_world(
        self,
        template_id: str,
        payload: Mapping[str, Any],
        *,
        run_id: str | None = None,
        time: str | None = None,
    ) -> Path:
        run_dir = create_world_from_template(
            template_id,
            payload,
            run_id=run_id,
            data_root=self.data_root,
            templates_root=self.templates_root,
        )
        generate_visualization_snapshot(run_dir, time=time)
        return run_dir

    def submit_director_event(
        self,
        run_dir: str | Path,
        payload: Mapping[str, Any],
        *,
        time: str | None = None,
    ):
        event = create_director_event(
            run_dir, payload, templates_root=self.templates_root
        )
        resolve_director_events(run_dir, templates_root=self.templates_root)
        generate_visualization_snapshot(run_dir, time=time)
        return event

    def add_character(
        self,
        run_dir: str | Path,
        request: Mapping[str, Any],
        *,
        current_stage: Any | None = None,
        active_world: Any | None = None,
        time: str | None = None,
    ):
        """Add a character and, when ``active_world`` is given, refresh its roster.

        ``active_world`` is the running simulation (anything exposing
        ``add_agent_from_data`` and optionally ``clock``). Without it only the
        run files change and a running world admits the newcomer at its next week
        start. The snapshot is labelled ``time``, else the active world's time.
        """
        result = add_character_to_world(
            run_dir,
            request,
            current_stage=current_stage,
            templates_root=self.templates_root,
            active_world=active_world,
        )
        resolve_director_events(run_dir, templates_root=self.templates_root)
        generate_visualization_snapshot(
            run_dir, time=time or _active_world_time(active_world)
        )
        return result

    def advance_to_safe_point(
        self, run_dir: str | Path, *, time: str | None = None
    ) -> dict:
        resolve_director_events(run_dir, templates_root=self.templates_root)
        return generate_visualization_snapshot(run_dir, time=time)
