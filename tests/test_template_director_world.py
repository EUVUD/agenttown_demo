from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.config import load_config

load_config(Path(__file__).resolve().parents[1] / "config.example.json")

from src.world.clock import Stage
from src.world.director import (
    DirectorValidationError,
    create_director_event,
    resolve_director_events,
)
from src.world.director_service import DirectorWorldService
from src.world.template_world import (
    CharacterEntryError,
    add_character_to_world,
    create_world_from_template,
)
from src.world.templates import TemplateRegistry, TemplateValidationError
from src.world.visualization import generate_visualization_snapshot


class TemplateDirectorWorldTests(unittest.TestCase):
    def test_loads_school_template_and_creator_schema(self) -> None:
        registry = TemplateRegistry()

        template = registry.load("school-classroom")
        schema = registry.get_creator_schema("school-classroom")

        self.assertEqual(template.template_id, "school-classroom")
        self.assertIn("student", template.role_archetypes)
        self.assertIn("transfer_student", template.join_modes)
        self.assertIn("rumor", template.director_event_types)
        self.assertIn("role_archetypes", schema)
        self.assertIn("character_fields", schema)
        self.assertIn("roleplay", template.prompt_fragments)

    def test_template_validation_rejects_unknown_and_malformed_templates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad = root / "bad-template"
            bad.mkdir()
            (bad / "template.json").write_text(
                json.dumps({"id": "bad-template"}), encoding="utf-8"
            )
            registry = TemplateRegistry(root=root)

            with self.assertRaises(TemplateValidationError):
                registry.load("missing-template")
            with self.assertRaises(TemplateValidationError):
                registry.load("bad-template")

    def test_create_world_from_school_template_validates_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "data"
            payload = {
                "world": {"class_name": "Class 2-3", "school_name": "North High"},
                "characters": [
                    {
                        "name": "Lin",
                        "role": "student",
                        "gender": "female",
                        "brief_introduction": "Quiet transfer student.",
                        "appearance_and_impression": "Short hair and clean uniform.",
                        "personality": "Careful and observant.",
                        "motivation": "Find a place in the class.",
                    }
                ],
            }

            run_dir = create_world_from_template(
                "school-classroom",
                payload,
                run_id="01010000",
                data_root=data_root,
            )

            self.assertTrue((run_dir / "worldview.json").exists())
            self.assertTrue((run_dir / "locations.json").exists())
            self.assertTrue((run_dir / "template_meta.json").exists())
            self.assertTrue(
                (run_dir / "persona" / "Lin" / "profile" / "year=2020.json").exists()
            )
            self.assertTrue((run_dir / "persona" / "Lin" / "state.jsonl").exists())

            invalid = {"world": {"class_name": "Class 2-3"}, "characters": []}
            with self.assertRaises(TemplateValidationError):
                create_world_from_template(
                    "school-classroom",
                    invalid,
                    run_id="01010001",
                    data_root=data_root,
                )

    def test_director_events_validate_persist_and_resolve_without_state_edits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._make_world(Path(tmp) / "data")

            event = create_director_event(
                run_dir,
                {
                    "type": "rumor",
                    "timing": "Y2020-W01-begin",
                    "targets": ["Lin"],
                    "visibility": "class",
                    "intensity": 3,
                    "locations": ["classroom"],
                    "duration": {"weeks": 1},
                    "description": "A rumor spreads before morning reading.",
                },
            )
            self.assertEqual(event.type, "rumor")
            self.assertTrue((run_dir / "director" / "events.jsonl").exists())

            with self.assertRaises(DirectorValidationError):
                create_director_event(
                    run_dir,
                    {
                        "type": "rumor",
                        "timing": "Y2020-W01-begin",
                        "description": "Direct edit attempt.",
                        "vitality": 10,
                    },
                )

            results = resolve_director_events(run_dir)
            self.assertEqual(results[0].status, "applied")
            self.assertIn("rumor", results[0].produced_inputs)

    def test_add_character_entry_initializes_storage_and_rejects_unsafe_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._make_world(Path(tmp) / "data")

            entry = add_character_to_world(
                run_dir,
                {
                    "join_mode": "transfer_student",
                    "character": {
                        "name": "Mina",
                        "role": "student",
                        "gender": "female",
                        "brief_introduction": "New student from another city.",
                        "appearance_and_impression": "Tidy uniform and bright eyes.",
                        "personality": "Curious and direct.",
                        "motivation": "Understand the class quickly.",
                    },
                    "arrival_context": "Arrives before Monday homeroom.",
                    "known_character_hints": [
                        {"name": "Lin", "context": "Met during entrance paperwork."}
                    ],
                },
                current_stage=Stage.BEGIN,
            )

            persona = run_dir / "persona" / "Mina"
            self.assertEqual(entry.character_name, "Mina")
            self.assertTrue((persona / "profile" / "year=2020.json").exists())
            self.assertTrue((persona / "memory" / "scratchpad" / "general.jsonl").exists())
            self.assertTrue(
                (persona / "memory" / "scratchpad" / "characters" / "Lin.jsonl").exists()
            )

            with self.assertRaises(CharacterEntryError):
                add_character_to_world(
                    run_dir,
                    {
                        "join_mode": "transfer_student",
                        "character": {
                            "name": "Kai",
                            "role": "student",
                            "gender": "male",
                            "brief_introduction": "Late arrival.",
                            "appearance_and_impression": "Nervous posture.",
                            "personality": "Reserved.",
                            "motivation": "Avoid attention.",
                        },
                    },
                    current_stage=Stage.ACTIVITY,
                )

    def test_visualization_snapshot_and_service_flow_are_client_friendly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = DirectorWorldService(data_root=Path(tmp) / "data")
            run_dir = service.create_world(
                "school-classroom",
                {
                    "world": {"class_name": "Class 2-3", "school_name": "North High"},
                    "characters": [
                        {
                            "name": "Lin",
                            "role": "student",
                            "gender": "female",
                            "brief_introduction": "Quiet transfer student.",
                            "appearance_and_impression": "Short hair.",
                            "personality": "Careful.",
                            "motivation": "Settle in.",
                        }
                    ],
                },
                run_id="01010000",
            )
            service.submit_director_event(
                run_dir,
                {
                    "type": "opportunity",
                    "timing": "Y2020-W01-begin",
                    "targets": ["Lin"],
                    "visibility": "class",
                    "intensity": 2,
                    "locations": ["classroom"],
                    "duration": {"weeks": 1},
                    "description": "The teacher asks Lin to lead a small display.",
                },
            )
            service.add_character(
                run_dir,
                {
                    "join_mode": "transfer_student",
                    "character": {
                        "name": "Mina",
                        "role": "student",
                        "gender": "female",
                        "brief_introduction": "New student.",
                        "appearance_and_impression": "Tidy uniform.",
                        "personality": "Curious.",
                        "motivation": "Make friends.",
                    },
                },
            )

            snapshot = generate_visualization_snapshot(run_dir)
            self.assertIn("timeline_events", snapshot)
            self.assertIn("characters", snapshot)
            self.assertIn("relationships", snapshot)
            self.assertIn("locations", snapshot)
            self.assertIn("director_event_results", snapshot)
            self.assertEqual({c["name"] for c in snapshot["characters"]}, {"Lin", "Mina"})
            self.assertNotIn("prompt", json.dumps(snapshot))
            self.assertTrue((run_dir / "visualization" / "current.json").exists())

    def _make_world(self, data_root: Path) -> Path:
        return create_world_from_template(
            "school-classroom",
            {
                "world": {"class_name": "Class 2-3", "school_name": "North High"},
                "characters": [
                    {
                        "name": "Lin",
                        "role": "student",
                        "gender": "female",
                        "brief_introduction": "Quiet transfer student.",
                        "appearance_and_impression": "Short hair and clean uniform.",
                        "personality": "Careful and observant.",
                        "motivation": "Find a place in the class.",
                    }
                ],
            },
            run_id="01010000",
            data_root=data_root,
        )


if __name__ == "__main__":
    unittest.main()
