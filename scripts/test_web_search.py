"""
Скрипт для ручной проверки интеграции веб-поиска через OpenRouter.

Выполняет РЕАЛЬНЫЕ запросы к API, расходует кредиты OpenRouter + стоимость
поиска (Exa по умолчанию, ~$0.012 за запрос при max_results=3).

Проверяет:
  1. Что при выключенном web_search tool не подключается, цитаты не приходят.
  2. Что при включённом web_search для "свежего" вопроса возвращаются
     `annotations` со ссылками на источники (= поиск реально произошёл).
  3. Что для "болтовни" модель НЕ получает ссылок (экономия токенов).
  4. Что итоговый ответ OpenAIClient содержит блок "🔗 Источники:" при
     наличии цитат.

Примечание про `server_tool_use.web_search_requests`:
  OpenRouter заполняет это поле ТОЛЬКО при native-поиске провайдера
  (OpenAI, Anthropic, xAI, Perplexity). Для `engine=exa` поле остаётся
  пустым, даже когда поиск реально выполнялся. Поэтому основной критерий
  "поиск был" — наличие цитат (`annotations`), а не `search_requests`.

Использование:
    python scripts/test_web_search.py
    python scripts/test_web_search.py --model google/gemini-2.5-flash
    python scripts/test_web_search.py --engine auto
    python scripts/test_web_search.py --only fresh
    python scripts/test_web_search.py --verbose
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from dataclasses import dataclass
from typing import Optional

# Добавляем корень проекта в path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

from openai_client.client import OpenAIClient

load_dotenv()


# (категория, вопрос, ожидается_поиск)
#   - "fresh" — вопросы, требующие свежих данных → модель должна искать
#   - "chat"  — болтовня / общие вопросы → модель искать НЕ должна
TEST_CASES: list[tuple[str, str, bool]] = [
    ("fresh", "Какая сейчас погода в Москве?", True),
    ("fresh", "Какие последние новости про OpenAI за эту неделю?", True),
    ("fresh", "Какой сегодняшний курс доллара к рублю?", True),
    ("chat", "Расскажи короткий анекдот про программиста.", False),
    ("chat", "Чем питон отличается от жавы в двух словах?", False),
    ("chat", "Посоветуй как расслабиться после работы.", False),
]


@dataclass
class CaseResult:
    """Итог одного прогона вопроса."""
    category: str
    question: str
    expected_search: bool
    web_enabled: bool
    answer: str
    search_requests: int          # usage.server_tool_use.web_search_requests
    citations: list[dict]         # извлечённые annotations
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    has_sources_block: bool       # есть ли "🔗 Источники:" в тексте ответа
    error: Optional[str] = None


# ---------------------------------------------------------------------------- #
# Вспомогательные функции                                                      #
# ---------------------------------------------------------------------------- #

async def _ask_with_diagnostics(
    client: OpenAIClient, question: str, web_enabled: bool
) -> tuple[str, dict]:
    """
    Вызывает ``answer_question_simple``, предварительно переключив флаг
    web_search. Чтобы получить сырой ``usage`` и ``annotations`` без
    дублирования запроса, делаем ОДИН прямой вызов chat.completions и руками
    выполняем ту же постобработку, что и в клиенте (блок источников + лог).
    
    Возвращает (итоговый_ответ, диагностика_dict).
    """
    from openai_client.prompts import SIMPLE_QUESTION_SYSTEM_PROMPT, WEB_SEARCH_RULE_SUFFIX

    # Временно переключаем флаг (в этом скрипте клиент используется
    # одним вызовом, race condition не грозит).
    prev = client.get_web_search_enabled()
    client.set_web_search_enabled(web_enabled)

    try:
        system_content = SIMPLE_QUESTION_SYSTEM_PROMPT
        if web_enabled:
            system_content += WEB_SEARCH_RULE_SUFFIX
            system_content += client._current_date_hint()
        
        request_kwargs = {
            "model": client.model,
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": question},
            ],
            "max_tokens": client.inline_max_tokens,
            "temperature": 0.3,
        }
        tool = client._build_web_search_tool()
        if tool is not None:
            request_kwargs["extra_body"] = {"tools": [tool]}

        start = time.monotonic()
        response = await client.client.chat.completions.create(**request_kwargs)
        latency_ms = (time.monotonic() - start) * 1000

        raw_answer = response.choices[0].message.content or ""

        # Те же шаги постобработки, что в production-коде
        citations = client._extract_annotations(response)
        sources_block = client._format_sources_block(citations)
        final_answer = (
            f"{raw_answer}\n{sources_block}" if sources_block else raw_answer
        )

        # Счётчик поисковых запросов
        search_requests = 0
        try:
            dump = response.model_dump() if hasattr(response, "model_dump") else {}
            search_requests = int(
                (dump.get("usage") or {})
                .get("server_tool_use", {})
                .get("web_search_requests", 0)
            )
        except Exception:
            pass

        usage = getattr(response, "usage", None)

        diag = {
            "latency_ms": latency_ms,
            "search_requests": search_requests,
            "citations": citations,
            "prompt_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
            "completion_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
            "total_tokens": getattr(usage, "total_tokens", 0) if usage else 0,
            "model_used": getattr(response, "model", client.model),
            "finish_reason": response.choices[0].finish_reason,
            "has_sources_block": bool(sources_block),
        }
        return final_answer, diag

    finally:
        client.set_web_search_enabled(prev)


async def _run_case(
    client: OpenAIClient,
    category: str,
    question: str,
    expected_search: bool,
    web_enabled: bool,
) -> CaseResult:
    """Прогон одного вопроса с одним режимом (web on/off)."""
    try:
        answer, diag = await _ask_with_diagnostics(client, question, web_enabled)
        return CaseResult(
            category=category,
            question=question,
            expected_search=expected_search,
            web_enabled=web_enabled,
            answer=answer,
            search_requests=diag["search_requests"],
            citations=diag["citations"],
            prompt_tokens=diag["prompt_tokens"],
            completion_tokens=diag["completion_tokens"],
            total_tokens=diag["total_tokens"],
            latency_ms=diag["latency_ms"],
            has_sources_block=diag["has_sources_block"],
        )
    except Exception as e:
        return CaseResult(
            category=category,
            question=question,
            expected_search=expected_search,
            web_enabled=web_enabled,
            answer="",
            search_requests=0,
            citations=[],
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            latency_ms=0,
            has_sources_block=False,
            error=f"{type(e).__name__}: {e}",
        )


# ---------------------------------------------------------------------------- #
# Печать                                                                       #
# ---------------------------------------------------------------------------- #

def _truncate(text: str, limit: int = 280) -> str:
    text = (text or "").strip().replace("\n", " ")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _print_case(r: CaseResult, verbose: bool) -> None:
    tag_web = "WEB ON " if r.web_enabled else "WEB OFF"
    cat_tag = r.category.upper()

    # Основной индикатор "поиск был" — наличие цитат (annotations).
    # ``search_requests`` из usage.server_tool_use заполняется только
    # для native-поиска провайдера; у Exa он всегда 0, поэтому
    # верифицируем по citations.
    search_happened = len(r.citations) > 0 or r.search_requests > 0

    verdict = "✅"
    verdict_notes: list[str] = []

    if r.error:
        verdict = "❌"
        verdict_notes.append(f"ошибка: {r.error}")
    else:
        # Если web выключен — ни поисков, ни цитат быть не должно
        if not r.web_enabled and search_happened:
            verdict = "❌"
            verdict_notes.append("цитаты/поиск при выключенном web")

        # Если web включён — сверяем с ожиданием по смыслу
        if r.web_enabled:
            if r.expected_search and not search_happened:
                verdict = "⚠️"
                verdict_notes.append("ожидали поиск, но цитат/поисков не было")
            if not r.expected_search and search_happened:
                verdict = "⚠️"
                verdict_notes.append("болтовня, а модель всё равно искала")

    print(f"{verdict} [{cat_tag} | {tag_web}] {r.question}")
    print(
        f"   поиск: {r.search_requests}  |  цитат: {len(r.citations)}  |  "
        f"tokens: prompt={r.prompt_tokens} compl={r.completion_tokens} "
        f"total={r.total_tokens}  |  {r.latency_ms:.0f} мс"
    )
    if verdict_notes:
        for note in verdict_notes:
            print(f"   ⚠️  {note}")
    if not r.error:
        print(f"   ответ: {_truncate(r.answer, 280)}")
    if verbose and r.citations:
        for i, c in enumerate(r.citations[:5], 1):
            print(f"     [{i}] {c.get('title') or '(без заголовка)'} — {c.get('url')}")
    print()


def _print_summary(results: list[CaseResult]) -> None:
    print("=" * 72)
    print("ИТОГО")
    print("=" * 72)

    total = len(results)
    errors = [r for r in results if r.error]
    total_tokens = sum(r.total_tokens for r in results)
    total_searches = sum(r.search_requests for r in results)
    total_citations = sum(len(r.citations) for r in results)

    def _searched(r: CaseResult) -> bool:
        return len(r.citations) > 0 or r.search_requests > 0

    ok_fresh = sum(
        1 for r in results
        if r.category == "fresh" and r.web_enabled
        and _searched(r) and not r.error
    )
    fresh_with_web = sum(
        1 for r in results if r.category == "fresh" and r.web_enabled
    )

    false_positives = sum(
        1 for r in results
        if r.category == "chat" and r.web_enabled
        and _searched(r) and not r.error
    )
    chat_with_web = sum(
        1 for r in results if r.category == "chat" and r.web_enabled
    )

    leaks = sum(1 for r in results if not r.web_enabled and _searched(r))

    print(f"  прогонов:              {total}")
    print(f"  ошибок API:            {len(errors)}")
    print(f"  суммарно токенов:      {total_tokens}")
    print(f"  суммарно цитат:        {total_citations}")
    print(
        f"  суммарно поисков (SR): {total_searches}  "
        "(заполняется только для native engine)"
    )
    print(
        f"  fresh + web → поиск:   {ok_fresh}/{fresh_with_web} "
        f"({'✅ все свежие вопросы триггернули поиск' if fresh_with_web and ok_fresh == fresh_with_web else '⚠️ часть свежих вопросов не триггернула поиск'})"
    )
    print(
        f"  chat + web без поиска: {chat_with_web - false_positives}/{chat_with_web} "
        f"(экономия токенов на болтовне)"
    )
    if leaks:
        print(f"  ❌ УТЕЧКИ (поиск при web_off): {leaks}")
    if errors:
        print("\n  Ошибки:")
        for r in errors:
            print(f"    [{r.category}/{('ON' if r.web_enabled else 'OFF')}] "
                  f"{r.question} → {r.error}")
    print()


# ---------------------------------------------------------------------------- #
# main                                                                         #
# ---------------------------------------------------------------------------- #

async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Реальная проверка интеграции OpenRouter web search"
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Модель (по умолчанию — OPENAI_MODEL из .env)",
    )
    parser.add_argument(
        "--engine",
        default=None,
        help="Движок поиска: auto|native|exa|firecrawl|parallel "
             "(по умолчанию — WEB_SEARCH_ENGINE из .env или exa)",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=None,
        help="max_results per search call (по умолчанию — из .env или 3)",
    )
    parser.add_argument(
        "--max-total-results",
        type=int,
        default=None,
        help="max_total_results per request (по умолчанию — из .env или 3)",
    )
    parser.add_argument(
        "--context-size",
        default=None,
        choices=["low", "medium", "high"],
        help="search_context_size (по умолчанию — из .env или low)",
    )
    parser.add_argument(
        "--only",
        choices=["fresh", "chat", "all"],
        default="all",
        help="Какую категорию вопросов гонять (default: all)",
    )
    parser.add_argument(
        "--skip-off",
        action="store_true",
        help="Не прогонять контрольные запросы с выключенным web_search",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Печатать список источников для каждого ответа",
    )
    args = parser.parse_args()

    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    model = args.model or os.getenv("OPENAI_MODEL", "google/gemini-2.5-flash")
    engine = args.engine or os.getenv("WEB_SEARCH_ENGINE", "exa")
    max_results = args.max_results or int(os.getenv("WEB_SEARCH_MAX_RESULTS", "3"))
    max_total = args.max_total_results or int(os.getenv("WEB_SEARCH_MAX_TOTAL_RESULTS", "3"))
    context_size = args.context_size or os.getenv("WEB_SEARCH_CONTEXT_SIZE", "low")

    if not api_key:
        print("❌ Ошибка: OPENAI_API_KEY не задан в .env", file=sys.stderr)
        return 1

    if not base_url or "openrouter.ai" not in base_url:
        print(
            "⚠️  OPENAI_BASE_URL не указывает на OpenRouter "
            f"(сейчас: {base_url!r}).\n"
            "   openrouter:web_search tool будет молча проигнорирован "
            "другими провайдерами.\n"
            "   Продолжаю — скрипт покажет нулевое количество поисков.",
            file=sys.stderr,
        )

    # Минимальный уровень логирования клиента, чтобы не мешал печати скрипта
    logging.basicConfig(level=logging.WARNING)

    client = OpenAIClient(
        api_key=api_key,
        base_url=base_url,
        model=model,
        inline_max_tokens=500,
        timezone=os.getenv("TIMEZONE") or None,
        web_search_enabled=False,  # мы сами будем переключать на каждом вопросе
        web_search_engine=engine,
        web_search_max_results=max_results,
        web_search_max_total_results=max_total,
        web_search_context_size=context_size,
    )

    print(f"Base URL: {base_url or '(default)'}")
    print(f"Модель:   {model}")
    print(
        f"Web:      engine={engine}  max_results={max_results}  "
        f"max_total={max_total}  context_size={context_size}"
    )
    print(f"Тестов:   {len(TEST_CASES)} вопросов "
          f"× {'1' if args.skip_off else '2'} режим(а)\n")

    # Фильтрация по категории
    cases = [c for c in TEST_CASES if args.only == "all" or c[0] == args.only]

    results: list[CaseResult] = []

    # 1) Сначала прогон с web_search=ON для всех выбранных вопросов
    for category, question, expected_search in cases:
        r = await _run_case(client, category, question, expected_search, web_enabled=True)
        _print_case(r, verbose=args.verbose)
        results.append(r)

    # 2) Контрольный прогон с web_search=OFF (убеждаемся, что поиск не идёт)
    if not args.skip_off:
        print("— Контрольный прогон с WEB_SEARCH=OFF —\n")
        # Достаточно 2 вопросов, чтобы не жечь лишние токены
        control_cases = cases[:2]
        for category, question, expected_search in control_cases:
            r = await _run_case(
                client, category, question, expected_search, web_enabled=False
            )
            _print_case(r, verbose=args.verbose)
            results.append(r)

    _print_summary(results)

    # Код возврата:
    # 0 — всё ок
    # 1 — были ошибки API или утечки (цитаты/поиск при WEB OFF)
    has_errors = any(r.error for r in results)
    has_leaks = any(
        not r.web_enabled and (len(r.citations) > 0 or r.search_requests > 0)
        for r in results
    )
    return 1 if (has_errors or has_leaks) else 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\nПрервано пользователем")
        sys.exit(130)
