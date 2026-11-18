"""Service for exercise taxonomy lookups, in-memory caching, and fuzzy alias resolution."""

from typing import Any
import uuid
from rapidfuzz import fuzz, process
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.exercise import ExerciseAlias, StrengthExercise
from src.scripts.seed_exercises import EXERCISE_DEFINITIONS


class CatalogExerciseEntry:
    """In-memory lightweight representation of a catalog exercise with aliases."""

    def __init__(
        self,
        id: uuid.UUID,
        canonical_name: str,
        slug: str,
        category: str,
        primary_muscle_group: str,
        is_bodyweight: bool,
        default_unit: str,
        aliases: list[str],
    ):
        self.id = id
        self.canonical_name = canonical_name
        self.slug = slug
        self.category = category
        self.primary_muscle_group = primary_muscle_group
        self.is_bodyweight = is_bodyweight
        self.default_unit = default_unit
        self.aliases = aliases


class ExerciseCatalogService:
    """Manages exercise taxonomy, caching, and fuzzy alias resolution."""

    def __init__(self):
        self._entries: list[CatalogExerciseEntry] = []
        self._alias_to_entry: dict[str, CatalogExerciseEntry] = {}
        self._all_alias_strings: list[str] = []
        self._is_initialized = False

    def initialize_from_definitions(self):
        """Initializes catalog cache from static definitions (fallback/testing)."""
        self._entries.clear()
        self._alias_to_entry.clear()
        self._all_alias_strings.clear()

        for defn in EXERCISE_DEFINITIONS:
            # Deterministic namespace UUID based on slug
            entry_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"coach3.exercise.{defn['slug']}")
            entry = CatalogExerciseEntry(
                id=entry_id,
                canonical_name=defn["canonical_name"],
                slug=defn["slug"],
                category=defn["category"],
                primary_muscle_group=defn["primary_muscle_group"],
                is_bodyweight=defn["is_bodyweight"],
                default_unit=defn["default_unit"],
                aliases=[a.lower().strip() for a in defn["aliases"]],
            )
            self._entries.append(entry)

            # Map canonical name and aliases
            canonical_key = entry.canonical_name.lower().strip()
            self._alias_to_entry[canonical_key] = entry
            self._all_alias_strings.append(canonical_key)

            for alias in entry.aliases:
                self._alias_to_entry[alias] = entry
                self._all_alias_strings.append(alias)

        self._is_initialized = True

    async def load_from_db(self, session: AsyncSession):
        """Loads and refreshes catalog cache from database."""
        q = select(StrengthExercise).options(selectinload(StrengthExercise.aliases))
        res = await session.execute(q)
        exercises = res.scalars().all()

        if not exercises:
            # Fallback to definitions
            self.initialize_from_definitions()
            return

        self._entries.clear()
        self._alias_to_entry.clear()
        self._all_alias_strings.clear()

        for ex in exercises:
            aliases = [a.alias.lower().strip() for a in ex.aliases]
            entry = CatalogExerciseEntry(
                id=ex.id,
                canonical_name=ex.canonical_name,
                slug=ex.slug,
                category=ex.category,
                primary_muscle_group=ex.primary_muscle_group,
                is_bodyweight=ex.is_bodyweight,
                default_unit=ex.default_unit,
                aliases=aliases,
            )
            self._entries.append(entry)

            canonical_key = entry.canonical_name.lower().strip()
            self._alias_to_entry[canonical_key] = entry
            self._all_alias_strings.append(canonical_key)

            for alias in entry.aliases:
                self._alias_to_entry[alias] = entry
                self._all_alias_strings.append(alias)

        self._is_initialized = True

    def find_match(
        self,
        query: str,
        min_score: float = 75.0,
    ) -> tuple[CatalogExerciseEntry | None, float, list[tuple[CatalogExerciseEntry, float]]]:
        """Resolves spoken query to canonical exercise using exact & fuzzy alias matching.

        Returns:
            (best_match, best_score, list_of_top_alternatives)
        """
        if not self._is_initialized:
            self.initialize_from_definitions()

        cleaned_query = query.lower().strip()
        if not cleaned_query:
            return None, 0.0, []

        # 1. Exact match check
        if cleaned_query in self._alias_to_entry:
            return self._alias_to_entry[cleaned_query], 100.0, []

        # 2. Fuzzy match across all aliases and canonical names
        matches = process.extract(
            cleaned_query,
            self._all_alias_strings,
            scorer=fuzz.token_sort_ratio,
            limit=5,
        )

        if not matches:
            return None, 0.0, []

        best_alias, best_score, _ = matches[0]
        best_entry = self._alias_to_entry[best_alias]

        # Gather distinct alternative exercises
        seen_ids = {best_entry.id}
        alternatives = []
        for alias, score, _ in matches[1:]:
            cand_entry = self._alias_to_entry[alias]
            if cand_entry.id not in seen_ids:
                seen_ids.add(cand_entry.id)
                alternatives.append((cand_entry, float(score)))

        if best_score >= min_score:
            return best_entry, float(best_score), alternatives
        else:
            # Below confidence threshold: return top candidate as alternative for review
            all_alternatives = [(best_entry, float(best_score))] + alternatives
            return None, float(best_score), all_alternatives

    def get_all_entries(self) -> list[CatalogExerciseEntry]:
        if not self._is_initialized:
            self.initialize_from_definitions()
        return list(self._entries)


# Global singleton instance
catalog_service = ExerciseCatalogService()
