import io
import re
from pathlib import Path


def extract_text_from_pdf(content: bytes) -> str:
    """Извлекает текст из PDF через pypdf."""
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(content))
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text.strip())
        return "\n\n".join(pages)
    except Exception as e:
        return f"[Ошибка извлечения текста из PDF: {e}]"


def extract_text_from_docx(content: bytes) -> str:
    """Извлекает текст из DOCX через python-docx."""
    try:
        from docx import Document
        doc = Document(io.BytesIO(content))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]

        # Таблицы тоже важны
        for table in doc.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells:
                    paragraphs.append(" | ".join(cells))

        return "\n\n".join(paragraphs)
    except Exception as e:
        return f"[Ошибка извлечения текста из DOCX: {e}]"


def extract_text_from_bpmn(content: bytes) -> str:
    """Извлекает читаемое описание из BPMN XML."""
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(content)

        ns = {
            'bpmn': 'http://www.omg.org/spec/BPMN/20100524/MODEL',
            'camunda': 'http://camunda.org/schema/1.0/bpmn',
        }

        elements = []

        # Задачи
        for tag in ['userTask', 'serviceTask', 'task', 'manualTask', 'scriptTask']:
            for el in root.iter(f"{{{ns['bpmn']}}}{tag}"):
                name = el.get('name', el.get('id', 'без названия'))
                elements.append(f"[{tag}] {name}")

        # События
        for tag in ['startEvent', 'endEvent', 'intermediateCatchEvent']:
            for el in root.iter(f"{{{ns['bpmn']}}}{tag}"):
                name = el.get('name', el.get('id', ''))
                elements.append(f"[{tag}] {name}")

        # Шлюзы
        for tag in ['exclusiveGateway', 'parallelGateway', 'inclusiveGateway']:
            for el in root.iter(f"{{{ns['bpmn']}}}{tag}"):
                name = el.get('name', el.get('id', ''))
                elements.append(f"[{tag}] {name}")

        # Потоки с условиями
        for flow in root.iter(f"{{{ns['bpmn']}}}sequenceFlow"):
            name = flow.get('name', '')
            src = flow.get('sourceRef', '')
            tgt = flow.get('targetRef', '')
            if name:
                elements.append(f"[flow] {src} → {tgt} ({name})")

        raw_xml = content.decode('utf-8', errors='replace')
        return f"BPMN-схема содержит:\n" + "\n".join(elements) + \
               f"\n\n--- RAW XML (первые 3000 символов) ---\n{raw_xml[:3000]}"

    except Exception as e:
        raw = content.decode('utf-8', errors='replace')
        return f"[Ошибка парсинга BPMN: {e}]\n\nRaw XML:\n{raw[:2000]}"


def get_file_type(filename: str, content_type: str) -> str:
    """Определяет тип файла."""
    ext = Path(filename).suffix.lower().lstrip('.')
    mapping = {
        'pdf':  'pdf',
        'docx': 'docx',
        'doc':  'docx',
        'bpmn': 'bpmn',
        'xml':  'bpmn',
        'png':  'image',
        'jpg':  'image',
        'jpeg': 'image',
        'webp': 'image',
    }
    if ext in mapping:
        return mapping[ext]
    if 'image' in content_type:
        return 'image'
    if 'pdf' in content_type:
        return 'pdf'
    return 'unknown'


def extract_text(content: bytes, filename: str, content_type: str) -> str:
    """Роутер: выбирает нужный экстрактор по типу файла."""
    file_type = get_file_type(filename, content_type)

    if file_type == 'pdf':
        return extract_text_from_pdf(content)
    elif file_type == 'docx':
        return extract_text_from_docx(content)
    elif file_type == 'bpmn':
        return extract_text_from_bpmn(content)
    elif file_type == 'image':
        return ""  # изображения обрабатываются через Vision API отдельно
    else:
        # Попытка прочитать как текст
        try:
            return content.decode('utf-8', errors='replace')[:5000]
        except Exception:
            return "[Не удалось извлечь текст из файла]"


def truncate_text(text: str, max_chars: int = 12000) -> str:
    """Обрезает текст до максимального размера с пометкой."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n\n[... текст обрезан, показаны первые {max_chars} символов]"
