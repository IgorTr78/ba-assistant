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

ЯЗЫК: ВСЕ названия задач, событий, шлюзов, дорожек и пула — ТОЛЬКО НА РУССКОМ ЯЗЫКЕ.
Например: "Проверка заявки", "Одобрено?", "Отправить уведомление", "Менеджер", "Клиент".
Никакого английского в атрибутах name="...".

ПРАВИЛА XML:
1. Namespace: xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
   Добавь: xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
           xmlns:camunda="http://camunda.org/schema/1.0/bpmn"
           xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
           xmlns:di="http://www.omg.org/spec/DD/20100524/DI"

2. ID элементов: Activity_XXXXXXX, Gateway_XXXXXXX, Event_XXXXXXX, Flow_XXXXXXX
   (7 случайных буквенно-цифровых символов, латиница — только для ID, не для name)

3. Обязательно включай <bpmndi:BPMNDiagram> с координатами для отображения в bpmn-js.

4. Стандартные размеры (BPMNShape):
   - Task:    width="120" height="80"   (шире для русского текста)
   - Gateway: width="50"  height="50"
   - Event:   width="36"  height="36"
   Шаг по X: 180px. Центр по Y в своей lane.

5. Если разные роли → используй lanes внутри одного pool. Названия lanes — на русском.

6. userTask — задача человека, serviceTask — автоматическая задача системы.

7. Каждый sequenceFlow: sourceRef и targetRef обязательны.
   Названия потоков (name="...") — на русском если есть условие (например: "Да", "Нет", "Одобрено").

8. Для шлюзов используй короткие вопросы: "Одобрено?", "Резидент?", "Ошибка?".

ФОРМАТ ОТВЕТА:

<bpmn_xml>
<?xml version="1.0" encoding="UTF-8"?>
<definitions ...>
  ...валидный XML с русскими названиями...
</definitions>
</bpmn_xml>

<description>
### Описание схемы
[участники, happy path, альтернативные пути — на русском]

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
        temperature=0.1,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": "Сгенерируй BPMN-схему на русском языке по указанным требованиям."},
        ],
    )

    raw = response.choices[0].message.content
    return _parse_bpmn_response(raw)


def _parse_bpmn_response(raw: str) -> dict:
    xml = ""
    description = ""

    xml_match = re.search(r"<bpmn_xml>(.*?)</bpmn_xml>", raw, re.DOTALL)
    if xml_match:
        xml = xml_match.group(1).strip()

    desc_match = re.search(r"<description>(.*?)</description>", raw, re.DOTALL)
    if desc_match:
        description = desc_match.group(1).strip()

    if not xml:
        xml_direct = re.search(r'(<\?xml.*?</definitions>)', raw, re.DOTALL)
        if xml_direct:
            xml = xml_direct.group(1).strip()
            description = raw.replace(xml, "").strip()

    return {"xml": xml, "description": description or raw}


def validate_bpmn_xml(xml: str) -> tuple[bool, str]:
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
