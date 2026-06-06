import os
import glob
import logging

logger = logging.getLogger(__name__)


async def load_domain_context(context_dir: str = "./context") -> str:
    """Scan context_dir for .md files, read them, and return concatenated text.

    Format:
    === File: business_rules.md ===
    <content>

    === File: definitions.md ===
    <content>
    """
    if not os.path.exists(context_dir):
        return ""

    md_files = sorted(glob.glob(os.path.join(context_dir, "*.md")))
    if not md_files:
        return ""

    parts = []
    for filepath in md_files:
        filename = os.path.basename(filepath)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if content:
                parts.append(f"=== File: {filename} === {content}")
        except Exception as e:
            logger.warning(f"Failed to read domain context file {filename}: {e}")

        return "".join(parts)
