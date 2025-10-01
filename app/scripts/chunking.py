import re
import uuid

SPEAKER_REGEX = re.compile(r"^([A-Z][a-zA-Z\.]*(?:\s[A-Z][a-zA-Z\.]*)*):\s")

def speaker_level_chunks(lines, section=None, start_chunk_id=0, global_state=None):
    """
    Merge lines per speaker into paragraphs, skipping moderator/unknown,
    assign a globally unique chunk_id, track start/end page & line numbers,
    and ignore text before first known speaker.

    Additional logic:
    - Track if moderator appears across sections.
    - Track the very first speaker (before moderator).
    - If moderator never appears, drop ALL contributions from that speaker.
    - Remove any speaker who ever says "First question".
    """
    if global_state is None:
        global_state = {"moderator_found": False, "first_speaker": None, "exclude_speakers": set()}

    merged = []
    current_speaker = None
    current_para = []
    start_page = start_line = end_page = end_line = None
    chunk_id = start_chunk_id

    for line in lines:
        text = line["text"].strip()
        page = line["page"]
        line_no = line.get("line")

        # Track moderator presence
        if "moderator" in text.lower():
            global_state["moderator_found"] = True
            continue

        # Does line start with a speaker?
        match = SPEAKER_REGEX.match(text)
        if match:
            speaker = match.group(1).strip()
            text_after = text[match.end():].strip()

            # Capture the very first speaker globally (only once)
            if global_state["first_speaker"] is None:
                global_state["first_speaker"] = speaker

            # If speaker says "First question", mark them for exclusion
            if "first question" in text.lower():
                global_state["exclude_speakers"].add(speaker)
                continue

            # Save the previous speaker paragraph if valid and not excluded
            if current_para and current_speaker not in (None, "Unknown"):
                if current_speaker not in global_state["exclude_speakers"] and not (
                    not global_state["moderator_found"] and current_speaker == global_state["first_speaker"]
                ):
                    merged.append({
                        "chunk_id": f"{section}_{chunk_id}" if section else chunk_id,
                        "speaker": current_speaker,
                        "text": " ".join(current_para).strip(),
                        "start_page": start_page,
                        "end_page": end_page,
                        "start_line": start_line,
                        "end_line": end_line,
                        "section": section
                    })
                chunk_id += 1
                current_para = []

            # Start new speaker
            current_speaker = speaker
            start_page, start_line = page, line_no
            end_page, end_line = page, line_no

            if text_after:
                current_para.append(text_after)

        else:
            # Not a new speaker line → append only if inside a known speaker and not excluded
            if current_speaker not in (None, "Unknown") and current_speaker not in global_state["exclude_speakers"]:
                current_para.append(text)
                end_page, end_line = page, line_no

    # Save last paragraph if valid
    if current_para and current_speaker not in (None, "Unknown") and current_speaker not in global_state["exclude_speakers"]:
        if not (not global_state["moderator_found"] and current_speaker == global_state["first_speaker"]):
            merged.append({
                "chunk_id": f"{section}_{chunk_id}" if section else chunk_id,
                "speaker": current_speaker,
                "text": " ".join(current_para).strip(),
                "start_page": start_page,
                "end_page": end_page,
                "start_line": start_line,
                "end_line": end_line,
                "section": section
            })

    return merged, chunk_id, global_state


def chunk_metadata(metadata_lines, chunk_size=500, overlap=50, start_chunk_id=0):
    """
    Chunk metadata into ~chunk_size word chunks with overlap.
    Returns (chunks, next_chunk_id).
    """
    chunks = []
    words = []
    chunk_id = start_chunk_id

    # Flatten metadata lines into word list
    for line in metadata_lines:
        words.extend(line["text"].split())

    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_words = words[start:end]

        chunks.append({
            "chunk_id": f"Metadata_{chunk_id}",
            "text": " ".join(chunk_words),
            "section": "Metadata"
        })
        chunk_id += 1

        if end == len(words):  # last chunk
            break
        start = end - overlap  # shift back for overlap

    return chunks, chunk_id
