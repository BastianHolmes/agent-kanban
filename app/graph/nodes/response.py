import logging

from app.graph.state import AgentState

logger = logging.getLogger(__name__)


def response_node(state: AgentState) -> dict:
    error = state.get("error")
    if error:
        return {"response": f"Ошибка: {error}", "sources": []}

    response = state.get("response", "")
    sources = state.get("sources", [])

    if sources:
        refs = []
        seen = set()
        for s in sources:
            ref_key = f"{s['type']}:{s['ref']}"
            if ref_key in seen:
                continue
            seen.add(ref_key)

            if s["type"] == "card":
                refs.append(f"- Карточка [{s['ref']}]")
            elif s["type"] == "doc":
                refs.append(f"- Документ: {s.get('title', s['ref'])}")
            elif s["type"] == "code":
                refs.append(f"- Файл: `{s['ref']}`")

        if refs:
            response += "\n\n**Источники:**\n" + "\n".join(refs)

    return {"response": response}
