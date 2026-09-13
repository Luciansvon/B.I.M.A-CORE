def public_failure(context: str) -> str:
    return f"FAILED|{context}. Detail teknis dicatat di log."


def public_message(context: str) -> str:
    return f"❌ {context}. Detail teknis dicatat di log."
