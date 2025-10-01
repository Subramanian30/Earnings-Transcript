from rapidfuzz import fuzz
import re

SPEAKER_REGEX = re.compile(r"^([A-Z][a-zA-Z\.]*(?:\s[A-Z][a-zA-Z\.]*)*):\s")

OPENING_PHRASES = [
    "ladies and gentlemen",
    "good morning",
    "good afternoon",
    "good evening",
    "welcome everyone",
]

QA_CUES = [
    "first question",
    "we will now begin the q&a",
    "begin the question-and-answer",
    "let's open the line for questions",
    "we'll now take questions",
    "we'll move to q&a",
    "analysts may now ask their questions",
]


def split_transcript_metadata_opening_qa(lines):
    metadata, opening_remarks, qa = [], [], []

    first_opening_found = False
    remainder = []

    # Step 1️⃣ Split metadata vs transcript body
    for line in lines:
        text = line["text"].strip()
        speaker_match = SPEAKER_REGEX.match(text)

        # Speaker identified (Moderator/Operator/Coordinator, etc.)
        if speaker_match:
            speaker_name = speaker_match.group(1).lower()
            if any(role in speaker_name for role in ["moderator", "coordinator"]):
                first_opening_found = True
                remainder.append(line)
                continue

        # Phrase-based detection (no strict speaker needed)
        lowered = text.lower()
        if not first_opening_found:
            if any(fuzz.partial_ratio(lowered, phrase) > 85 for phrase in OPENING_PHRASES):
                first_opening_found = True
                remainder.append(line)
            else:
                metadata.append(line)
        else:
            remainder.append(line)

    if not first_opening_found:
        # No moderator/operator or opening phrase → everything is metadata
        return metadata, [], []

    # Step 2️⃣ Detect Q&A start
    split_index = None
    for i, row in enumerate(remainder):
        lowered = row["text"].lower()
        if any(fuzz.partial_ratio(lowered, cue) > 85 for cue in QA_CUES):
            split_index = i
            break

    if split_index is not None:
        opening_remarks = remainder[:split_index]
        qa = remainder[split_index:]
    else:
        opening_remarks = remainder
        qa = []

    return metadata, opening_remarks, qa
