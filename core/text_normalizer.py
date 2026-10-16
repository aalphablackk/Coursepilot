import re


def normalize_generated_text(text: str) -> str:
    """Remove em dashes from generated text without changing other content."""
    if not text:
        return text

    # Replace an em dash with a comma when it separates clauses.
    text = text.replace("—", ",")

    # Clean up spaces before punctuation.
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)

    # Avoid duplicate commas caused by normalization.
    text = re.sub(r",\s*,+", ",", text)

    return text