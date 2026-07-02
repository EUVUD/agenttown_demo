from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping


class TemplateValidationError(ValueError):
    """Raised when a world template or creator payload is invalid."""


@dataclass(frozen=True)
class WorldTemplate:
    template_id: str
    name: str
    version: str
    description: str
    time: Dict[str, Any]
    world_fields: Dict[str, Any]
    character_fields: Dict[str, Any]
    role_archetypes: Dict[str, Any]
    location_archetypes: Dict[str, Any]
    director_event_types: Dict[str, Any]
    join_modes: Dict[str, Any]
    visualization_hints: Dict[str, Any]
    default_state: Dict[str, Any]
    prompt_fragments: Dict[str, str]
    root: Path

    @property
    def creator_schema(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "name": self.name,
            "description": self.description,
            "time": self.time,
            "world_fields": self.world_fields,
            "character_fields": self.character_fields,
            "role_archetypes": self.role_archetypes,
            "join_modes": self.join_modes,
            "director_event_types": self.director_event_types,
            "visualization_hints": self.visualization_hints,
        }


class TemplateRegistry:
    """Load and validate declarative world template packs."""

    REQUIRED_SECTIONS = (
        "id",
        "name",
        "version",
        "time",
        "world_fields",
        "character_fields",
        "role_archetypes",
        "location_archetypes",
        "director_event_types",
        "join_modes",
        "visualization_hints",
    )

    def __init__(self, root: str | Path = "data/world_templates") -> None:
        self.root = Path(root)

    def load(self, template_id: str) -> WorldTemplate:
        template_dir = self.root / template_id
        template_path = template_dir / "template.json"
        if not template_path.exists():
            raise TemplateValidationError(f"unknown world template: {template_id}")

        try:
            raw = json.loads(template_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise TemplateValidationError(
                f"invalid JSON in template {template_id}: {exc}"
            ) from exc

        self._validate_template_shape(raw, template_id)
        prompt_fragments = self._load_prompt_fragments(template_dir)

        return WorldTemplate(
            template_id=str(raw["id"]),
            name=str(raw["name"]),
            version=str(raw["version"]),
            description=str(raw.get("description", "")),
            time=dict(raw["time"]),
            world_fields=dict(raw["world_fields"]),
            character_fields=dict(raw["character_fields"]),
            role_archetypes=dict(raw["role_archetypes"]),
            location_archetypes=dict(raw["location_archetypes"]),
            director_event_types=dict(raw["director_event_types"]),
            join_modes=dict(raw["join_modes"]),
            visualization_hints=dict(raw["visualization_hints"]),
            default_state=dict(raw.get("default_state", {})),
            prompt_fragments=prompt_fragments,
            root=template_dir,
        )

    def list_templates(self) -> List[str]:
        if not self.root.exists():
            return []
        return sorted(p.name for p in self.root.iterdir() if p.is_dir())

    def get_creator_schema(self, template_id: str) -> Dict[str, Any]:
        return self.load(template_id).creator_schema

    def validate_creator_payload(
        self, template_id: str, payload: Mapping[str, Any]
    ) -> None:
        template = self.load(template_id)
        self.validate_world_payload(template, payload.get("world", {}))
        characters = payload.get("characters")
        if not isinstance(characters, list) or not characters:
            raise TemplateValidationError("creator payload must include characters")
        for draft in characters:
            self.validate_character_draft(template, draft)

    def validate_world_payload(
        self, template: WorldTemplate, world_payload: Mapping[str, Any]
    ) -> None:
        if not isinstance(world_payload, Mapping):
            raise TemplateValidationError("world payload must be an object")
        missing = [
            field
            for field in template.world_fields.get("required", [])
            if field not in world_payload or world_payload[field] in ("", None)
        ]
        if missing:
            raise TemplateValidationError(
                f"missing required world fields: {', '.join(missing)}"
            )

    def validate_character_draft(
        self, template: WorldTemplate, draft: Mapping[str, Any]
    ) -> None:
        if not isinstance(draft, Mapping):
            raise TemplateValidationError("character draft must be an object")
        role = str(draft.get("role", "")).strip()
        if role not in template.role_archetypes:
            raise TemplateValidationError(f"unsupported role archetype: {role}")

        required = list(template.character_fields.get("required", []))
        role_fields = template.character_fields.get("by_role", {}).get(role, {})
        required.extend(role_fields.get("required", []))
        missing = [
            field for field in required if field not in draft or draft[field] in ("", None)
        ]
        if missing:
            raise TemplateValidationError(
                f"missing required character fields for {role}: {', '.join(missing)}"
            )

    def validate_join_mode(self, template: WorldTemplate, join_mode: str) -> None:
        if join_mode not in template.join_modes:
            raise TemplateValidationError(f"unsupported join mode: {join_mode}")

    def validate_event_type(self, template: WorldTemplate, event_type: str) -> None:
        if event_type not in template.director_event_types:
            raise TemplateValidationError(f"unsupported director event type: {event_type}")

    def _validate_template_shape(self, raw: Mapping[str, Any], template_id: str) -> None:
        missing = [section for section in self.REQUIRED_SECTIONS if section not in raw]
        if missing:
            raise TemplateValidationError(
                f"template {template_id} missing sections: {', '.join(missing)}"
            )
        if raw["id"] != template_id:
            raise TemplateValidationError(
                f"template id mismatch: expected {template_id}, got {raw['id']}"
            )
        for section in self.REQUIRED_SECTIONS:
            if section in {"id", "name", "version"}:
                continue
            if not isinstance(raw[section], dict):
                raise TemplateValidationError(f"template section must be object: {section}")

    def _load_prompt_fragments(self, template_dir: Path) -> Dict[str, str]:
        fragments: Dict[str, str] = {}
        worldview = template_dir / "worldview.md"
        if worldview.exists():
            fragments["worldview"] = worldview.read_text(encoding="utf-8")
        prompts_dir = template_dir / "prompts"
        if prompts_dir.exists():
            for path in sorted(prompts_dir.glob("*.md")):
                fragments[path.stem] = path.read_text(encoding="utf-8")
        return fragments
