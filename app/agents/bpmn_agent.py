import re
from openai import AsyncOpenAI
from app.core.config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

BPMN_PROMPT = """Ты — специалист по моделированию бизнес-процессов в нотации BPMN 2.0.
Генерируй валидный BPMN 2.0 XML, совместимый с Camunda и bpmn-js.

ПРОЕКТ: {project_name}
ТРЕБОВАНИЯ:
{requirements_text}

{existing_block}

ПРАВИЛА XML:
1. Namespace: xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
   Добавь: xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
           xmlns:camunda="http://camunda.org/schema/1.0/bpmn"
           xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
           xmlns:di="http://www.omg.org/spec/DD/20100524/DI"

2. ID элементов: Activity_XXXXXXX, Gateway_XXXXXXX, Event_XXXXXXX, Flow_XXXXXXX
   (7 случайных буквенно-цифровых символов)

3. Обязательно включай <bpmndi:BPMNDiagram> с координатами для отображения в bpmn-js.

4. Стандартные размеры (BPMNShape):
   - Task:    width="100" height="80"
   - Gateway: width="50"  height="50"
   - Event:   width="36"  height="36"
   Шаг по X: 150px. Центр по Y в своей lane.

5. Если разные роли → используй lanes внутри одного pool.

6. userTask — задача человека, serviceTask — автоматическая.

7. Каждый sequenceFlow: sourceRef и targetRef обязательны.

ФОРМАТ ОТВЕТА:

<bpmn_xml>
<?xml version="1.0" encoding="UTF-8"?>
<definitions ...>
  ...валидный XML...
</definitions>
</bpmn_xml>

<description>
### Описание схемы
[участники, happy path, альтернативные пути]

### Что осталось за рамками
[если требования неполные]

### Вопросы
[если нужно уточнение]
</description>"""


async def run_bpmn_agent(
    requirements_text: str,
    project_name: str,
    existing_bpmn_xml: str | None = None,
) -> dict:
    """
    Возвращает dict:
      {
        "xml": "<?xml ...>",
        "description": "Markdown-описание схемы"
      }
    """
    existing_block = ""
    if existing_bpmn_xml:
        existing_block = (
            f"СУЩЕСТВУЮЩАЯ СХЕМА (обнови её, не создавай с нуля):\n"
            f"```xml\n{existing_bpmn_xml[:3000]}\n```"
        )

    system = BPMN_PROMPT.format(
        project_name=project_name,
        requirements_text=requirements_text,
        existing_block=existing_block,
    )

    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        max_tokens=settings.OPENAI_MAX_TOKENS,
        temperature=0.1,    # низкая температура для валидного XML
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": "Сгенерируй BPMN-схему по указанным требованиям."},
        ],
    )

    raw = response.choices[0].message.content
    return _parse_bpmn_response(raw)


def _parse_bpmn_response(raw: str) -> dict:
    """Извлекает XML и описание из ответа модели."""
    xml = ""
    description = ""

    xml_match = re.search(r"<bpmn_xml>(.*?)</bpmn_xml>", raw, re.DOTALL)
    if xml_match:
        xml = xml_match.group(1).strip()

    desc_match = re.search(r"<description>(.*?)</description>", raw, re.DOTALL)
    if desc_match:
        description = desc_match.group(1).strip()

    # Фолбэк: если теги не найдены, ищем XML-блок напрямую
    if not xml:
        xml_direct = re.search(
            r'(<\?xml.*?</definitions>)',
            raw,
            re.DOTALL,
        )
        if xml_direct:
            xml = xml_direct.group(1).strip()
            description = raw.replace(xml, "").strip()

    return {"xml": xml, "description": description or raw}


def validate_bpmn_xml(xml: str) -> tuple[bool, str]:
    """Базовая валидация BPMN XML."""
    checks = [
        ('<definitions', "Отсутствует корневой элемент <definitions>"),
        ('</definitions>', "Незакрытый элемент <definitions>"),
        ('bpmndi:BPMNDiagram', "Отсутствует секция диаграммы BPMNDiagram"),
        ('startEvent', "Отсутствует стартовое событие"),
        ('endEvent', "Отсутствует конечное событие"),
    ]
    for tag, error in checks:
        if tag not in xml:
            return False, error
    return True, "OK"
