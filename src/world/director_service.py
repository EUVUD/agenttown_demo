from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from src.world.director import create_director_event, resolve_director_events
from src.world.template_world import add_character_to_world, create_world_from_template
from src.world.templates import TemplateRegistry
from src.world.visualization import generate_visualization_snapshot


class DirectorWorldService:
    """Small opt-in backend facade for template-driven director worlds."""

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
        self, template_id: str, payload: Mapping[str, Any], *, run_id: str | None = None
    ) -> Path:
        run_dir = create_world_from_template(
            template_id,
            payload,
            run_id=run_id,
            data_root=self.data_root,
            templates_root=self.templates_root,
        )
        generate_visualization_snapshot(run_dir)
        return run_dir

    def submit_director_event(self, run_dir: str | Path, payload: Mapping[str, Any]):
        event = create_director_event(
            run_dir, payload, templates_root=self.templates_root
        )
        resolve_director_events(run_dir, templates_root=self.templates_root)
        generate_visualization_snapshot(run_dir)
        return event

    def add_character(
        self,
        run_dir: str | Path,
        request: Mapping[str, Any],
        *,
        current_stage: Any = "BEGIN",
    ):
        result = add_character_to_world(
            run_dir,
            request,
            current_stage=current_stage,
            templates_root=self.templates_root,
        )
        resolve_director_events(run_dir, templates_root=self.templates_root)
        generate_visualization_snapshot(run_dir)
        return result

    def advance_to_safe_point(self, run_dir: str | Path) -> dict:
        resolve_director_events(run_dir, templates_root=self.templates_root)
        return generate_visualization_snapshot(run_dir)
