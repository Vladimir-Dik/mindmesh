# assistant_cli.py
# CLI интерфейс MindMesh, использует core.py

import core

ASSISTANT_VERSION = "assistant_cli_v1.0"

def ask(prompt, default=None, required=False):
    while True:
        v = input(f"{prompt}{' ['+default+']' if default else ''}: ").strip()
        if not v and default is not None:
            v = default
        if required and not v:
            print("Введите значение.")
            continue
        return v

def print_card_preview(preview):
    print("\n====== Карточка идеи ======")
    for k,v in preview.items():
        print(f"{k}: {v}")
    print("===========================\n")

def main():
    print("=== MindMesh — Ассистент (CLI) ===")
    print("1) Добавить идею")
    print("2) Выход")
    c = ask("Выбор", required=True)
    if c != "1":
        return

    print("\nОпиши идею свободным текстом (пустая строка — конец):")
    lines = []
    while True:
        l = input()
        if not l.strip():
            break
        lines.append(l)
    raw = "\n".join(lines)

    title = ask("Название идеи", required=True)
    short = ask("Краткое описание", required=True)
    full = ask("Полное описание", default=short, required=True)

    kw = ask("Ключевые слова (через запятую)", default="")
    kws_list = [x.strip() for x in kw.split(",") if x.strip()]

    print("\n=== Автор ===")
    name = ask("Имя", default="Unnamed", required=True)
    email = ask("Email", required=True)

    preview = {
        "Название": title,
        "Кратко": short,
        "Полное": full,
        "Ключевые слова": ", ".join(kws_list),
        "Автор": f"{name} <{email}>",
    }

    print_card_preview(preview)

    print("1) Сохранить")
    print("2) Отменить")
    c2 = ask("Выбор", required=True)
    if c2 != "1":
        print("Отменено.")
        return

    result = core.prepare_and_create_idea({
        "title": title,
        "short": short,
        "full": full,
        "keywords_list": kws_list,
        "raw_input": raw,
        "author_name": name,
        "author_email": email,
        "intake_mode": "LocalAssistant",
        "assistant_version": ASSISTANT_VERSION
    })

    print("\n[✓] Идея создана:", result["record_id"])
    print("Автор:", result["author_display"])
    print("Similarity:", result["similarity"])
    if result["duplicate_of"]:
        print("Дубликат:", result["duplicate_of"])

if __name__ == "__main__":
    main()
