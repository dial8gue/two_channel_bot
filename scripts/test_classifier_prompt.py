"""
Скрипт для тестирования QUESTION_CLASSIFIER_SYSTEM_PROMPT с разными моделями.

Отправляет набор тестовых вопросов (чат-вопросы и общие) на каждую модель
и сравнивает точность классификации.

Использование:
    python scripts/test_classifier_prompt.py
    python scripts/test_classifier_prompt.py --models gpt-4o-mini deepseek/deepseek-chat
    python scripts/test_classifier_prompt.py --runs 5
"""

import asyncio
import argparse
import os
import sys
import time
from dataclasses import dataclass

# Добавляем корень проекта в path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from openai import AsyncOpenAI

from openai_client.prompts import QUESTION_CLASSIFIER_SYSTEM_PROMPT

load_dotenv()


# Тестовые вопросы: (вопрос, ожидаемый_ответ)
TEST_CASES: list[tuple[str, str]] = [
    # --- CHAT вопросы ---
    ("Что обсуждали сегодня?", "CHAT"),
    ("О чём тут речь?", "CHAT"),
    ("Кто это написал?", "CHAT"),
    ("Что тут происходит?", "CHAT"),
    ("Кто больше всех писал?", "CHAT"),
    ("О чём говорили вчера?", "CHAT"),
    ("Что за срач был утром?", "CHAT"),
    ("Кто начал эту тему?", "CHAT"),
    ("Можешь пересказать что было?", "CHAT"),
    ("А что Вася писал?", "CHAT"),
    # --- GENERAL вопросы ---
    ("Какая погода в Москве?", "GENERAL"),
    ("Что такое Python?", "GENERAL"),
    ("Сколько будет 2+2?", "GENERAL"),
    ("Кто президент США?", "GENERAL"),
    ("Как приготовить борщ?", "GENERAL"),
    ("Что такое машинное обучение?", "GENERAL"),
    ("Переведи hello на русский", "GENERAL"),
    ("Расскажи анекдот", "GENERAL"),
    ("Какой сейчас курс доллара?", "GENERAL"),
    ("Посоветуй книгу", "GENERAL"),
]


@dataclass
class ModelResult:
    model: str
    correct: int
    total: int
    errors: list[str]
    avg_latency_ms: float
    details: list[dict]


async def classify_question(
    client: AsyncOpenAI, model: str, question: str, timeout: float = 15.0
) -> tuple[str, float]:
    """Классифицирует вопрос и возвращает (результат, время_мс)."""
    start = time.monotonic()
    response = await asyncio.wait_for(
        client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": QUESTION_CLASSIFIER_SYSTEM_PROMPT},
                {"role": "user", "content": question},
            ],
            max_tokens=10,
            temperature=0,
        ),
        timeout=timeout,
    )
    elapsed_ms = (time.monotonic() - start) * 1000
    raw = response.choices[0].message.content.strip().upper()

    # Парсим ответ так же как в клиенте
    if "GENERAL" in raw:
        return "GENERAL", elapsed_ms
    return "CHAT", elapsed_ms



async def _run_single_case(
    client: AsyncOpenAI, model: str, run_idx: int,
    question: str, expected: str, timeout: float,
) -> dict:
    """Запускает один тест-кейс и возвращает результат."""
    try:
        result, latency_ms = await classify_question(client, model, question, timeout)
        is_correct = result == expected
        error = None if is_correct else (
            f"  [run {run_idx+1}] «{question}» → {result} (ожидалось {expected})"
        )
        return {
            "run": run_idx + 1, "question": question, "expected": expected,
            "got": result, "correct": is_correct,
            "latency_ms": round(latency_ms, 1), "error": error,
        }
    except asyncio.TimeoutError:
        return {
            "run": run_idx + 1, "question": question, "expected": expected,
            "got": "TIMEOUT", "correct": False, "latency_ms": 0,
            "error": f"  [run {run_idx+1}] «{question}» → ТАЙМАУТ ({timeout}с)",
        }
    except Exception as e:
        return {
            "run": run_idx + 1, "question": question, "expected": expected,
            "got": "ERROR", "correct": False, "latency_ms": 0,
            "error": f"  [run {run_idx+1}] «{question}» → ОШИБКА: {e}",
        }


async def test_model(
    client: AsyncOpenAI, model: str, runs: int = 1, timeout: float = 15.0
) -> ModelResult:
    """Прогоняет все тест-кейсы по модели параллельно."""
    tasks = [
        _run_single_case(client, model, run_idx, question, expected, timeout)
        for run_idx in range(runs)
        for question, expected in TEST_CASES
    ]
    results = await asyncio.gather(*tasks)

    correct = sum(1 for r in results if r["correct"])
    total = len(results)
    errors = [r["error"] for r in results if r["error"]]
    latencies = [r["latency_ms"] for r in results if r["latency_ms"] > 0]

    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    return ModelResult(model, correct, total, errors, avg_latency, list(results))


def print_results(results: list[ModelResult]) -> None:
    """Выводит сводную таблицу результатов."""
    print("\n" + "=" * 70)
    print("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ QUESTION_CLASSIFIER_SYSTEM_PROMPT")
    print("=" * 70)

    # Сводная таблица
    print(f"\n{'Модель':<35} {'Точность':>10} {'Латенция':>12}")
    print("-" * 60)
    for r in sorted(results, key=lambda x: x.correct / max(x.total, 1), reverse=True):
        pct = (r.correct / r.total * 100) if r.total else 0
        print(f"{r.model:<35} {r.correct}/{r.total} ({pct:.0f}%) {r.avg_latency_ms:>8.0f} мс")

    # Детали ошибок
    for r in results:
        if r.errors:
            print(f"\nОшибки [{r.model}]:")
            for err in r.errors:
                print(err)

    print()


async def main():
    parser = argparse.ArgumentParser(
        description="Тестирование QUESTION_CLASSIFIER_SYSTEM_PROMPT"
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=None,
        help="Список моделей для тестирования",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Количество прогонов на каждую модель (default: 1)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="Таймаут на один запрос в секундах (default: 15)",
    )
    args = parser.parse_args()

    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    if not api_key:
        print("Ошибка: OPENAI_API_KEY не задан в .env")
        sys.exit(1)

    default_models = [
        os.getenv("CLASSIFIER_MODEL", "deepseek/deepseek-v3.2"),
        "google/gemini-2.5-flash",
    ]
    models = args.models or default_models

    client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    print(f"Base URL: {base_url}")
    print(f"Модели: {', '.join(models)}")
    print(f"Тест-кейсов: {len(TEST_CASES)} × {args.runs} прогон(ов)")
    print(f"Таймаут: {args.timeout}с на запрос")
    print(f"Промпт:\n{QUESTION_CLASSIFIER_SYSTEM_PROMPT}\n")

    results: list[ModelResult] = []
    for model in models:
        print(f"Тестирую {model}...", end=" ", flush=True)
        result = await test_model(client, model, runs=args.runs, timeout=args.timeout)
        pct = (result.correct / result.total * 100) if result.total else 0
        print(f"{pct:.0f}%")
        results.append(result)

    print_results(results)


if __name__ == "__main__":
    asyncio.run(main())
