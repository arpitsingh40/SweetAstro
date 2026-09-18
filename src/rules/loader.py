"""
Rule Catalog Loader.
Loads, validates, and indexes classical astrology rules from JSON definition files.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from .schema import ClassicalRule

logger = logging.getLogger("sweetastro.rules")


class RuleCatalog:
    def __init__(self):
        self.rules: Dict[str, ClassicalRule] = {}
        self.by_category: Dict[str, List[ClassicalRule]] = {
            "promise": [],
            "delay": [],
            "timing_dasha": [],
            "timing_transit": [],
            "jaimini": [],
            "stability": [],
        }

    def load_from_file(self, file_path: Path) -> int:
        """Loads and validates rules from a single JSON file.

        Files that do not contain a JSON list (e.g. lookup tables such as
        muhurta_rules.json) are skipped.
        """
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            logger.info("Skipping non-rule JSON file: %s", file_path.name)
            return 0

        count = 0
        for item in data:
            rule = ClassicalRule(**item)
            self.rules[rule.rule_id] = rule
            if rule.category in self.by_category:
                self.by_category[rule.category].append(rule)
            else:
                self.by_category[rule.category] = [rule]
            count += 1
        return count

    def load_from_directory(self, dir_path: Path) -> int:
        """Loads all .json rule files in a directory."""
        total = 0
        for json_file in dir_path.glob("*.json"):
            total += self.load_from_file(json_file)
        return total

    def get_rule(self, rule_id: str) -> Optional[ClassicalRule]:
        return self.rules.get(rule_id)

    def get_rules_by_category(self, category: str) -> List[ClassicalRule]:
        return self.by_category.get(category, [])
