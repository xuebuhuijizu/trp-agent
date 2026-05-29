from pathlib import Path

try:
    from docx import Document
except ImportError:
    Document = None


QUESTION_MARKS = ("?", "？")
MAX_FALLBACK_QUESTION_CHARS = 2000


def extract_questions(file_path: str | Path) -> list[str]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    suffix = path.suffix.lower()
    if suffix == ".docx":
        return _extract_from_docx(path)
    elif suffix == ".txt":
        return _extract_from_txt(path)
    else:
        raise ValueError(f"Unsupported file format: {suffix}")


def _extract_from_docx(path: Path) -> list[str]:
    if Document is None:
        raise ImportError("python-docx is required to parse .docx files")

    doc = Document(str(path))
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return _split_questions(text)


def _extract_from_txt(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return _split_questions(text)


def _split_questions(text: str) -> list[str]:
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    questions = []
    for line in lines:
        if line.endswith(QUESTION_MARKS):
            questions.append(line)
    if not questions:
        questions = [_cap_question(line) for line in lines if len(line) > 5]
    return questions or ([_cap_question(text.strip())] if text.strip() else [])


def _cap_question(text: str) -> str:
    if len(text) <= MAX_FALLBACK_QUESTION_CHARS:
        return text
    return text[:MAX_FALLBACK_QUESTION_CHARS].rstrip() + "..."
