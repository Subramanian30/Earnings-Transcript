import re
from typing import List, Dict

TOPIC_RE = re.compile(r"^-\s*Topic:\s*(.+)$")
SUMMARY_RE = re.compile(r"^\s*Summary:\s*(.+)$")


def parse_topics_block(block: str) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    current: Dict[str, str] = {}
    for line in (block or "").splitlines():
        line = line.rstrip()
        m_t = TOPIC_RE.match(line)
        if m_t:
            if current:
                items.append(current)
                current = {}
            current["topic"] = m_t.group(1).strip()
            continue
        m_s = SUMMARY_RE.match(line)
        if m_s:
            current["summary"] = m_s.group(1).strip()
            continue
    if current:
        items.append(current)
    # keep only well-formed
    return [it for it in items if it.get("topic")] 