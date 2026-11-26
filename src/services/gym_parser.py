"""Deterministic Natural Language Parsing Engine for Gym Mode."""

import re
from typing import Any, Literal
from src.schemas.gym import ExerciseRef, ParsedSetCandidate, ParsedStageResponse
from src.services.exercise_catalog import catalog_service

NUMBER_WORDS = {
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}

PLATE_MATH_LBS = {
    "one plate": 135.0,
    "a plate": 135.0,
    "1 plate": 135.0,
    "two plates": 225.0,
    "2 plates": 225.0,
    "three plates": 315.0,
    "3 plates": 315.0,
    "four plates": 405.0,
    "4 plates": 405.0,
    "five plates": 495.0,
    "5 plates": 495.0,
    "the bar": 45.0,
    "empty bar": 45.0,
}


class GymParser:
    """Parses spoken workout statements into structured sets and exercises."""

    def __init__(self):
        self.catalog = catalog_service

    def parse(self, transcript: str, default_unit: Literal["lbs", "kg"] = "lbs") -> ParsedStageResponse:
        cleaned_transcript = transcript.strip()
        if not cleaned_transcript:
            return ParsedStageResponse(
                raw_transcript="",
                parsed_sets=[],
                confidence_score=0.0,
                is_ambiguous=True,
            )

        # Check for multi-clause split (e.g. "followed by", "then", "and then")
        clauses = self._split_clauses(cleaned_transcript)
        parsed_candidates: list[ParsedSetCandidate] = []
        scores: list[float] = []
        is_ambiguous = False
        all_alternatives: list[ExerciseRef] = []

        for clause in clauses:
            cand, score, alts = self._parse_single_clause(clause, default_unit)
            if cand:
                parsed_candidates.append(cand)
                scores.append(score)
            else:
                is_ambiguous = True
                if score > 0:
                    scores.append(score)

            for alt_entry, _alt_score in alts:
                ref = ExerciseRef(
                    id=alt_entry.id,
                    canonical_name=alt_entry.canonical_name,
                    slug=alt_entry.slug,
                    category=alt_entry.category,
                    primary_muscle_group=alt_entry.primary_muscle_group,
                    is_bodyweight=alt_entry.is_bodyweight,
                    default_unit=alt_entry.default_unit,
                )
                if not any(a.id == ref.id for a in all_alternatives):
                    all_alternatives.append(ref)

        avg_confidence = sum(scores) / len(scores) / 100.0 if scores else 0.0
        avg_confidence = min(1.0, max(0.0, round(avg_confidence, 2)))

        return ParsedStageResponse(
            raw_transcript=cleaned_transcript,
            parsed_sets=parsed_candidates,
            confidence_score=avg_confidence,
            is_ambiguous=is_ambiguous or (len(parsed_candidates) == 0),
            alternative_exercises=all_alternatives[:3],
        )

    def _split_clauses(self, text: str) -> list[str]:
        # Split on "followed by", "and then", "then"
        parts = re.split(r"\b(?:followed by|and then|then)\b", text, flags=re.IGNORECASE)
        clauses = [p.strip() for p in parts if p.strip()]
        return clauses if clauses else [text]

    def _parse_single_clause(
        self, clause: str, default_unit: Literal["lbs", "kg"]
    ) -> tuple[ParsedSetCandidate | None, float, list[tuple[Any, float]]]:
        working_text = clause.lower()

        # 1. Extract RPE & Rest intervals
        rpe = None
        rpe_match = re.search(r"\b(?:at|felt like|with)?\s*rpe\s*(\d+(?:\.\d+)?)\b", working_text)
        if rpe_match:
            try:
                rpe = float(rpe_match.group(1))
                working_text = working_text.replace(rpe_match.group(0), " ")
            except ValueError:
                pass
        else:
            rir_match = re.search(r"\b(\d+)\s*(?:reps?\s*in\s*reserve|rir)\b", working_text)
            if rir_match:
                try:
                    rir = float(rir_match.group(1))
                    rpe = max(1.0, min(10.0, 10.0 - rir))
                    working_text = working_text.replace(rir_match.group(0), " ")
                except ValueError:
                    pass

        rest_seconds = None
        rest_match = re.search(r"\b(?:rest|rested|resting)?\s*(\d+)\s*(minutes?|mins?|seconds?|secs?)\b", working_text)
        if rest_match:
            val = int(rest_match.group(1))
            unit = rest_match.group(2)
            rest_seconds = val * 60 if "m" in unit else val
            working_text = working_text.replace(rest_match.group(0), " ")

        # 2. Extract Warmup flag
        is_warmup = False
        if re.search(r"\b(?:warmup|warm-up|warm up)\b", working_text):
            is_warmup = True
            working_text = re.sub(r"\b(?:warmup|warm-up|warm up)\b", " ", working_text)

        # 3. Plate Math check
        weight = 0.0
        weight_unit = default_unit
        plate_found = False
        for phrase, plate_lbs in PLATE_MATH_LBS.items():
            if phrase in working_text:
                weight = plate_lbs
                weight_unit = "lbs"
                plate_found = True
                working_text = working_text.replace(phrase, " ")
                break

        # 4. Bodyweight & Added Load check
        is_bodyweight = False
        added_weight = 0.0

        minus_match = re.search(r"\b(?:minus|-)\s*(\d+(?:\.\d+)?)\s*(?:lbs?|pounds?|kg|kilos?)?\b", working_text)
        if minus_match:
            is_bodyweight = True
            added_weight = -float(minus_match.group(1))
            working_text = working_text.replace(minus_match.group(0), " ")
            working_text = re.sub(r"\bassisted\b", " ", working_text)
        elif re.search(r"\bassisted\b", working_text):
            is_bodyweight = True
            working_text = re.sub(r"\bassisted\b", " ", working_text)
            asst_num_match = re.search(r"\b(?:at|with)?\s*(\d+(?:\.\d+)?)\s*(?:lbs?|pounds?|kg|kilos?)?\b", working_text)
            if asst_num_match:
                added_weight = -float(asst_num_match.group(1))
                working_text = working_text.replace(asst_num_match.group(0), " ")
        else:
            added_match = re.search(r"\b(?:with\s*(?:an?\s*)?(?:extra|plus)|extra|plus)\s*(\d+(?:\.\d+)?)\s*(?:lbs?|pounds?|kg|kilos?)?(?:\s*added)?\b", working_text)
            if added_match:
                is_bodyweight = True
                added_weight = float(added_match.group(1))
                working_text = working_text.replace(added_match.group(0), " ")
            elif "bodyweight only" in working_text or "bodyweight" in working_text:
                is_bodyweight = True
                added_weight = 0.0
                working_text = re.sub(r"\bbodyweight(?:\s*only)?\b", " ", working_text)

        # 5. Extract Standard Weight (if not plate math and not pure bodyweight)
        if not plate_found and added_weight == 0.0:
            # 5a. Preposition-prefixed weight: "at 225", "with 100 kg", "@ 185 lbs"
            prep_match = re.search(
                r"(?:(?:\b(?:at|with)\s*)|@\s*)(\d+(?:\.\d+)?)\s*(lbs?|pounds?|kg|kilos?)?\b",
                working_text,
            )
            if prep_match:
                val_str, u_str = prep_match.group(1), prep_match.group(2)
                weight = float(val_str)
                if u_str and ("kg" in u_str or "kilo" in u_str):
                    weight_unit = "kg"
                elif u_str and ("lb" in u_str or "pound" in u_str):
                    weight_unit = "lbs"
                else:
                    weight_unit = default_unit
                working_text = working_text[: prep_match.start()] + " " + working_text[prep_match.end() :]
            else:
                # 5b. Bare weight with explicit unit (no preposition required): "bench press 225 lbs 3x5", "225lb squat 5x5"
                bare_match = re.search(
                    r"\b(\d+(?:\.\d+)?)\s*(lbs?|pounds?|kg|kilos?)\b",
                    working_text,
                )
                if bare_match:
                    val_str, u_str = bare_match.group(1), bare_match.group(2)
                    weight = float(val_str)
                    weight_unit = "kg" if ("kg" in u_str or "kilo" in u_str) else "lbs"
                    working_text = working_text[: bare_match.start()] + " " + working_text[bare_match.end() :]
                else:
                    # 5c. Plural dumbbell weight e.g. "with 70s"
                    db_weight_match = re.search(r"\b(?:with|at)\s*(\d+)s\b", working_text)
                    if db_weight_match:
                        weight = float(db_weight_match.group(1))
                        weight_unit = default_unit
                        working_text = working_text[: db_weight_match.start()] + " " + working_text[db_weight_match.end() :]

        # 6. Sets and Reps extraction
        sets = 1
        reps = 1

        # Check single / double / triple / heavy single
        if re.search(r"\b(?:heavy\s*)?single\b", working_text):
            reps = 1
            sets = 1
            working_text = re.sub(r"\b(?:did\s*a\s*)?(?:heavy\s*)?single\b", " ", working_text)
        elif re.search(r"\b(?:heavy\s*)?double\b", working_text):
            reps = 2
            sets = 1
            working_text = re.sub(r"\b(?:did\s*a\s*)?(?:heavy\s*)?double\b", " ", working_text)
        elif re.search(r"\b(?:heavy\s*)?triple\b", working_text):
            reps = 3
            sets = 1
            working_text = re.sub(r"\b(?:did\s*a\s*)?(?:heavy\s*)?triple\b", " ", working_text)
        else:
            # Pattern: 3x5 or 3 * 5 or 5 by 10
            compact_match = re.search(r"\b(\d+)\s*(?:[xX*]|by)\s*(\d+)\b", working_text)
            if compact_match:
                sets = int(compact_match.group(1))
                reps = int(compact_match.group(2))
                working_text = working_text.replace(compact_match.group(0), " ")
            else:
                # Pattern: 5 sets by 8 reps or 3 sets of 5
                sets_reps_match = re.search(
                    r"\b(\d+|" + "|".join(NUMBER_WORDS.keys()) + r")\s*sets?\s*(?:of|by|\*|x)\s*(\d+|" + "|".join(NUMBER_WORDS.keys()) + r")(?:\s*reps?)?\b",
                    working_text,
                )
                if sets_reps_match:
                    s_str, r_str = sets_reps_match.group(1), sets_reps_match.group(2)
                    sets = int(s_str) if s_str.isdigit() else NUMBER_WORDS.get(s_str, 1)
                    reps = int(r_str) if r_str.isdigit() else NUMBER_WORDS.get(r_str, 1)
                    working_text = working_text.replace(sets_reps_match.group(0), " ")
                else:
                    # Pattern: set of 10 or 1 set of 10
                    set_of_match = re.search(
                        r"\b(?:a\s+)?sets?\s*(?:of|for)\s*(\d+|" + "|".join(NUMBER_WORDS.keys()) + r")(?:\s*reps?)?\b",
                        working_text,
                    )
                    if set_of_match:
                        sets = 1
                        r_str = set_of_match.group(1)
                        reps = int(r_str) if r_str.isdigit() else NUMBER_WORDS.get(r_str, 1)
                        working_text = working_text.replace(set_of_match.group(0), " ")
                    else:
                        # Pattern: 3 reps or 8 reps
                        reps_only_match = re.search(r"\b(\d+|" + "|".join(NUMBER_WORDS.keys()) + r")\s*reps?\b", working_text)
                        if reps_only_match:
                            r_str = reps_only_match.group(1)
                            reps = int(r_str) if r_str.isdigit() else NUMBER_WORDS.get(r_str, 1)
                            working_text = working_text.replace(reps_only_match.group(0), " ")

        # 7. Remaining text is the exercise name candidate
        # Clean filler words: "did", "on", "of", "with", "for", "lbs", "pounds", "kilos", "reps", "sets", "at", etc.
        filler = r"\b(?:did|i|just|on|of|for|lbs|pounds|kg|kilos|reps?|sets?|at|a|the|with|an|and|then|felt|like|my)\b"
        cleaned_exercise_str = re.sub(filler, " ", working_text)
        cleaned_exercise_str = re.sub(r"[^a-zA-Z\s-]", "", cleaned_exercise_str)
        cleaned_exercise_str = " ".join(cleaned_exercise_str.split())

        entry, score, alts = self.catalog.find_match(cleaned_exercise_str, min_score=70.0)
        if not entry:
            return None, score, alts

        # Determine is_bodyweight and weight defaults based on catalog definition
        is_bodyweight = is_bodyweight or entry.is_bodyweight
        if is_bodyweight:
            if added_weight == 0.0 and weight > 0.0:
                # If user said "30 lbs pullups", attribute 30 to added_weight
                added_weight = weight
                weight = 0.0

        candidate = ParsedSetCandidate(
            exercise_id=entry.id,
            exercise_name=entry.canonical_name,
            category=entry.category,
            sets=sets,
            reps=reps,
            weight=weight,
            weight_unit=weight_unit,
            is_bodyweight=is_bodyweight,
            added_weight=added_weight,
            rpe=rpe,
            is_warmup=is_warmup,
            rest_seconds=rest_seconds,
        )

        return candidate, score, alts


# Global singleton parser
gym_parser = GymParser()
