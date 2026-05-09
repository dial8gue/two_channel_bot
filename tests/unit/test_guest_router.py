"""
Unit tests for bot.routers.guest_router.

We test the ``on_guest_message`` handler directly (by extracting it from the
Router built by ``create_guest_router``) with fully mocked dependencies so
the tests don't require a live Telegram connection or aiogram's full
dispatcher machinery.
"""

from __future__ import annotations

import asyncio
from io import BytesIO
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.routers.guest_router import create_guest_router
from openai_client.client import OpenAIClientError


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _extract_handler(router):
    """Return the single registered guest_message callback from a Router."""
    handlers = router.guest_message.handlers
    assert len(handlers) == 1, "guest_router must register exactly one handler"
    return handlers[0].callback


def _make_config(
    *,
    guest_mode_enabled: bool = True,
    guest_debounce_seconds: int = 60,
):
    """Build a minimal Config-like stub sufficient for the handler."""
    cfg = MagicMock()
    cfg.guest_mode_enabled = guest_mode_enabled
    cfg.guest_debounce_seconds = guest_debounce_seconds
    return cfg


def _make_message(
    *,
    guest_query_id: Optional[str] = "gq-1",
    text: Optional[str] = "What's 2+2?",
    caption: Optional[str] = None,
    user_id: Optional[int] = 42,
    chat_id: Optional[int] = -100999,
    photo=None,
    reply_to_message=None,
    sticker=None,
    animation=None,
):
    """Build a Message-like stub with just enough surface for the handler."""
    message = MagicMock()
    message.guest_query_id = guest_query_id
    message.text = text
    message.caption = caption
    message.photo = photo or []
    message.sticker = sticker
    message.animation = animation
    message.reply_to_message = reply_to_message

    if user_id is not None:
        caller_user = MagicMock()
        caller_user.id = user_id
        message.guest_bot_caller_user = caller_user
    else:
        message.guest_bot_caller_user = None

    if chat_id is not None:
        caller_chat = MagicMock()
        caller_chat.id = chat_id
        message.guest_bot_caller_chat = caller_chat
        chat = MagicMock()
        chat.id = chat_id
        message.chat = chat
    else:
        message.guest_bot_caller_chat = None
        message.chat = None

    message.bot = AsyncMock()
    message.answer_guest_query = AsyncMock()
    return message


def _make_bot(username: str = "mybot"):
    """Build a Bot-like stub whose get_me() returns the given username."""
    bot = AsyncMock()
    me = MagicMock()
    me.username = username
    bot.get_me = AsyncMock(return_value=me)
    return bot


def _make_openai_client(
    *,
    vision_enabled: bool = False,
    answer: str = "Four.",
    answer_raises: Optional[Exception] = None,
    describe_image_result: str = "A photo of a cat.",
):
    """Build an OpenAIClient-like stub."""
    client = AsyncMock()
    client.vision_enabled = vision_enabled
    if answer_raises is not None:
        client.answer_question_simple = AsyncMock(side_effect=answer_raises)
    else:
        client.answer_question_simple = AsyncMock(return_value=answer)
    client.describe_image = AsyncMock(return_value=describe_image_result)
    return client


def _make_admin_service(
    *,
    guest_mode_override: Optional[bool] = None,
    guest_debounce_override: Optional[int] = None,
):
    """
    Build an AdminService-like stub.
    ``is_guest_mode_enabled`` returns None when no override is set, which
    means: fall back to the env default from Config.
    """
    svc = AsyncMock()
    svc.is_guest_mode_enabled = AsyncMock(return_value=guest_mode_override)
    svc.get_guest_debounce_seconds = AsyncMock(return_value=guest_debounce_override)
    return svc


def _make_debounce_manager(
    *,
    can_execute: bool = True,
    remaining: float = 0.0,
):
    """Build a DebounceManager-like stub."""
    mgr = AsyncMock()
    mgr.can_execute = AsyncMock(return_value=(can_execute, remaining))
    mgr.mark_executed = AsyncMock(return_value=None)
    return mgr


def _make_photo(file_id: str = "fid", width: int = 640, height: int = 480):
    """Build a PhotoSize-like stub."""
    photo = MagicMock()
    photo.file_id = file_id
    photo.width = width
    photo.height = height
    photo.file_size = 1000
    return photo


# --------------------------------------------------------------------------- #
# Router wiring                                                               #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_router_registers_exactly_one_guest_message_handler():
    """
    Regression guard: ``create_guest_router`` must attach exactly one handler
    to ``Router.guest_message`` — multiple handlers would compete for the
    single reply slot Telegram allows per guest query.
    """
    router = create_guest_router(_make_config())
    assert len(router.guest_message.handlers) == 1
    assert router.name == "guest_router"


# --------------------------------------------------------------------------- #
# Feature toggle                                                              #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.unit
async def test_handler_ignores_query_when_guest_mode_disabled_in_config():
    """
    No DB override, env config has guest_mode_enabled=False → the handler
    must short-circuit without calling OpenAI or replying.
    """
    router = create_guest_router(_make_config(guest_mode_enabled=False))
    handler = _extract_handler(router)

    message = _make_message()
    bot = _make_bot()
    openai_client = _make_openai_client()
    admin_service = _make_admin_service(guest_mode_override=None)
    debounce_manager = _make_debounce_manager()

    await handler(
        message=message,
        bot=bot,
        openai_client=openai_client,
        admin_service=admin_service,
        debounce_manager=debounce_manager,
        config=_make_config(guest_mode_enabled=False),
    )

    openai_client.answer_question_simple.assert_not_awaited()
    message.answer_guest_query.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_handler_ignores_query_when_db_override_disables_guest_mode():
    """
    DB-stored override (False) must win over an enabled env default (True).
    """
    cfg = _make_config(guest_mode_enabled=True)
    router = create_guest_router(cfg)
    handler = _extract_handler(router)

    message = _make_message()
    bot = _make_bot()
    openai_client = _make_openai_client()
    admin_service = _make_admin_service(guest_mode_override=False)
    debounce_manager = _make_debounce_manager()

    await handler(
        message=message,
        bot=bot,
        openai_client=openai_client,
        admin_service=admin_service,
        debounce_manager=debounce_manager,
        config=cfg,
    )

    openai_client.answer_question_simple.assert_not_awaited()
    message.answer_guest_query.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_handler_runs_when_db_override_enables_guest_mode_over_env():
    """DB override (True) beats env default (False)."""
    cfg = _make_config(guest_mode_enabled=False)
    router = create_guest_router(cfg)
    handler = _extract_handler(router)

    message = _make_message(text="Hi @mybot what is 2+2?")
    bot = _make_bot(username="mybot")
    openai_client = _make_openai_client(answer="Four.")
    admin_service = _make_admin_service(guest_mode_override=True)
    debounce_manager = _make_debounce_manager()

    await handler(
        message=message,
        bot=bot,
        openai_client=openai_client,
        admin_service=admin_service,
        debounce_manager=debounce_manager,
        config=cfg,
    )

    openai_client.answer_question_simple.assert_awaited_once()
    message.answer_guest_query.assert_called_once()


# --------------------------------------------------------------------------- #
# Debounce                                                                    #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.unit
async def test_handler_replies_with_warning_when_user_is_debounced():
    """
    When the per-user debounce blocks the request, the handler must send a
    user-visible warning (not silently drop) and must NOT call OpenAI.
    
    Each guest query has its own reply slot, so spending this one on a
    throttling notice is harmless — the user will still get a fresh slot
    for their next real mention.
    """
    cfg = _make_config(guest_debounce_seconds=60)
    router = create_guest_router(cfg)
    handler = _extract_handler(router)

    message = _make_message()
    bot = _make_bot()
    openai_client = _make_openai_client()
    admin_service = _make_admin_service()
    debounce_manager = _make_debounce_manager(can_execute=False, remaining=42.0)

    await handler(
        message=message,
        bot=bot,
        openai_client=openai_client,
        admin_service=admin_service,
        debounce_manager=debounce_manager,
        config=cfg,
    )

    openai_client.answer_question_simple.assert_not_awaited()
    debounce_manager.mark_executed.assert_not_awaited()
    message.answer_guest_query.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_handler_uses_db_override_for_debounce_interval():
    """
    Debounce interval from the DB (if > 0) wins over the env default.
    We assert the exact value passed to ``can_execute``.
    """
    cfg = _make_config(guest_debounce_seconds=60)
    router = create_guest_router(cfg)
    handler = _extract_handler(router)

    message = _make_message()
    bot = _make_bot()
    openai_client = _make_openai_client()
    admin_service = _make_admin_service(guest_debounce_override=15)
    debounce_manager = _make_debounce_manager()

    await handler(
        message=message,
        bot=bot,
        openai_client=openai_client,
        admin_service=admin_service,
        debounce_manager=debounce_manager,
        config=cfg,
    )

    # Called with (operation_key, interval_seconds); interval must be the override
    assert debounce_manager.can_execute.call_args.args[1] == 15
    # And the key is namespaced by user id to keep per-user independence.
    assert debounce_manager.can_execute.call_args.args[0] == "guest:42"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_handler_marks_debounce_executed_only_on_successful_reply():
    """
    On successful reply the user's debounce budget should be consumed.
    """
    cfg = _make_config()
    router = create_guest_router(cfg)
    handler = _extract_handler(router)

    message = _make_message()
    bot = _make_bot()
    openai_client = _make_openai_client(answer="ok")
    admin_service = _make_admin_service()
    debounce_manager = _make_debounce_manager()

    await handler(
        message=message,
        bot=bot,
        openai_client=openai_client,
        admin_service=admin_service,
        debounce_manager=debounce_manager,
        config=cfg,
    )

    debounce_manager.mark_executed.assert_awaited_once_with("guest:42")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_handler_does_not_mark_executed_when_openai_fails():
    """
    If OpenAI raises, the debounce budget must NOT be consumed — otherwise
    a failing backend would silently lock the user out.
    """
    cfg = _make_config()
    router = create_guest_router(cfg)
    handler = _extract_handler(router)

    message = _make_message()
    bot = _make_bot()
    openai_client = _make_openai_client(
        answer_raises=OpenAIClientError("boom")
    )
    admin_service = _make_admin_service()
    debounce_manager = _make_debounce_manager()

    await handler(
        message=message,
        bot=bot,
        openai_client=openai_client,
        admin_service=admin_service,
        debounce_manager=debounce_manager,
        config=cfg,
    )

    debounce_manager.mark_executed.assert_not_awaited()


# --------------------------------------------------------------------------- #
# Prompt construction                                                         #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.unit
async def test_handler_strips_bot_mention_before_calling_openai():
    """
    The ``@mybot`` mention is routing metadata, not part of the question —
    it must be removed before the prompt reaches the model.
    """
    cfg = _make_config()
    router = create_guest_router(cfg)
    handler = _extract_handler(router)

    message = _make_message(text="@mybot What is the capital of France?")
    bot = _make_bot(username="mybot")
    openai_client = _make_openai_client(answer="Paris.")
    admin_service = _make_admin_service()
    debounce_manager = _make_debounce_manager()

    await handler(
        message=message,
        bot=bot,
        openai_client=openai_client,
        admin_service=admin_service,
        debounce_manager=debounce_manager,
        config=cfg,
    )

    asked_question = openai_client.answer_question_simple.call_args.args[0]
    assert "@mybot" not in asked_question
    assert "capital of France" in asked_question


@pytest.mark.asyncio
@pytest.mark.unit
async def test_handler_skips_query_with_only_mention_and_no_text():
    """
    A bare ``@mybot`` mention with no actual text and no media shouldn't
    trigger a model call — there's nothing to answer.
    """
    cfg = _make_config()
    router = create_guest_router(cfg)
    handler = _extract_handler(router)

    message = _make_message(text="@mybot")
    bot = _make_bot(username="mybot")
    openai_client = _make_openai_client()
    admin_service = _make_admin_service()
    debounce_manager = _make_debounce_manager()

    await handler(
        message=message,
        bot=bot,
        openai_client=openai_client,
        admin_service=admin_service,
        debounce_manager=debounce_manager,
        config=cfg,
    )

    openai_client.answer_question_simple.assert_not_awaited()
    message.answer_guest_query.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_handler_uses_default_prompt_when_only_photo_attached():
    """
    When the user replies with only a photo/sticker/GIF (no text), the
    handler should fall back to a generic ``"Что на этом изображении?"``
    prompt rather than bailing out.
    """
    cfg = _make_config()
    router = create_guest_router(cfg)
    handler = _extract_handler(router)

    photo = _make_photo()
    message = _make_message(text=None, caption=None, photo=[photo])
    bot = _make_bot(username="mybot")
    openai_client = _make_openai_client(
        vision_enabled=True,
        answer="It's a cat.",
        describe_image_result="A black cat on a sofa.",
    )
    admin_service = _make_admin_service()
    debounce_manager = _make_debounce_manager()

    # Stub BytesIO download so we don't hit the network
    async def fake_download(_photo, destination):
        destination.write(b"\x00\x01\x02")
    message.bot.download = AsyncMock(side_effect=fake_download)

    await handler(
        message=message,
        bot=bot,
        openai_client=openai_client,
        admin_service=admin_service,
        debounce_manager=debounce_manager,
        config=cfg,
    )

    asked_question = openai_client.answer_question_simple.call_args.args[0]
    assert "Что на этом изображении" in asked_question


# --------------------------------------------------------------------------- #
# Vision                                                                      #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.unit
async def test_handler_attaches_image_description_when_vision_enabled():
    """
    With a photo attached and vision enabled, ``describe_image`` output must
    be appended to the prompt so the text model has the context.
    """
    cfg = _make_config()
    router = create_guest_router(cfg)
    handler = _extract_handler(router)

    photo = _make_photo()
    message = _make_message(
        text="@mybot what's this?",
        photo=[photo],
    )
    bot = _make_bot(username="mybot")
    openai_client = _make_openai_client(
        vision_enabled=True,
        answer="It's a cat.",
        describe_image_result="A black cat on a sofa.",
    )
    admin_service = _make_admin_service()
    debounce_manager = _make_debounce_manager()

    async def fake_download(_photo, destination):
        destination.write(b"\x00")
    message.bot.download = AsyncMock(side_effect=fake_download)

    await handler(
        message=message,
        bot=bot,
        openai_client=openai_client,
        admin_service=admin_service,
        debounce_manager=debounce_manager,
        config=cfg,
    )

    openai_client.describe_image.assert_awaited_once()
    asked_question = openai_client.answer_question_simple.call_args.args[0]
    assert "A black cat on a sofa." in asked_question
    assert "what's this?" in asked_question


@pytest.mark.asyncio
@pytest.mark.unit
async def test_handler_skips_vision_when_disabled_even_if_photo_present():
    """
    With a photo attached but vision disabled, ``describe_image`` must NOT
    be called, and the prompt must contain only the user's text.
    """
    cfg = _make_config()
    router = create_guest_router(cfg)
    handler = _extract_handler(router)

    photo = _make_photo()
    message = _make_message(
        text="@mybot what's this?",
        photo=[photo],
    )
    bot = _make_bot(username="mybot")
    openai_client = _make_openai_client(vision_enabled=False, answer="idk")
    admin_service = _make_admin_service()
    debounce_manager = _make_debounce_manager()

    await handler(
        message=message,
        bot=bot,
        openai_client=openai_client,
        admin_service=admin_service,
        debounce_manager=debounce_manager,
        config=cfg,
    )

    openai_client.describe_image.assert_not_awaited()
    asked_question = openai_client.answer_question_simple.call_args.args[0]
    assert "[Изображение" not in asked_question


@pytest.mark.asyncio
@pytest.mark.unit
async def test_handler_describes_image_from_replied_to_message():
    """
    If the guest message has no photo of its own but replies to a message
    with a photo, vision should still run on that replied photo.
    """
    cfg = _make_config()
    router = create_guest_router(cfg)
    handler = _extract_handler(router)

    replied = MagicMock()
    replied.photo = [_make_photo(file_id="fid-in-reply")]

    message = _make_message(
        text="@mybot describe this",
        photo=[],
        reply_to_message=replied,
    )
    bot = _make_bot(username="mybot")
    openai_client = _make_openai_client(
        vision_enabled=True,
        answer="It's a dog.",
        describe_image_result="A golden retriever.",
    )
    admin_service = _make_admin_service()
    debounce_manager = _make_debounce_manager()

    async def fake_download(_photo, destination):
        destination.write(b"\x00")
    message.bot.download = AsyncMock(side_effect=fake_download)

    await handler(
        message=message,
        bot=bot,
        openai_client=openai_client,
        admin_service=admin_service,
        debounce_manager=debounce_manager,
        config=cfg,
    )

    openai_client.describe_image.assert_awaited_once()
    asked_question = openai_client.answer_question_simple.call_args.args[0]
    assert "A golden retriever." in asked_question


@pytest.mark.asyncio
@pytest.mark.unit
async def test_handler_proceeds_when_vision_fails_with_openai_error():
    """
    A failing ``describe_image`` call must not fail the whole handler — the
    text prompt should still reach the model (sans image context).
    """
    cfg = _make_config()
    router = create_guest_router(cfg)
    handler = _extract_handler(router)

    photo = _make_photo()
    message = _make_message(
        text="@mybot what's this?",
        photo=[photo],
    )
    bot = _make_bot(username="mybot")
    openai_client = _make_openai_client(
        vision_enabled=True,
        answer="I don't have vision data but here's my guess.",
    )
    openai_client.describe_image = AsyncMock(
        side_effect=OpenAIClientError("vision timed out")
    )
    admin_service = _make_admin_service()
    debounce_manager = _make_debounce_manager()

    async def fake_download(_photo, destination):
        destination.write(b"\x00")
    message.bot.download = AsyncMock(side_effect=fake_download)

    await handler(
        message=message,
        bot=bot,
        openai_client=openai_client,
        admin_service=admin_service,
        debounce_manager=debounce_manager,
        config=cfg,
    )

    # Text model still called, and reply still sent
    openai_client.answer_question_simple.assert_awaited_once()
    message.answer_guest_query.assert_called_once()
    asked_question = openai_client.answer_question_simple.call_args.args[0]
    assert "[Изображение" not in asked_question


# --------------------------------------------------------------------------- #
# Reply path                                                                  #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.unit
async def test_handler_wraps_reply_in_inline_query_result_article():
    """
    Bot API 10.0 requires ``answerGuestQuery.result`` to be an
    ``InlineQueryResult``. We check that the handler passes exactly such an
    object with the model's answer as the message body.
    """
    from aiogram.types import InlineQueryResultArticle, InputTextMessageContent

    cfg = _make_config()
    router = create_guest_router(cfg)
    handler = _extract_handler(router)

    message = _make_message(text="@mybot hi")
    bot = _make_bot(username="mybot")
    openai_client = _make_openai_client(answer="Hello, world!")
    admin_service = _make_admin_service()
    debounce_manager = _make_debounce_manager()

    await handler(
        message=message,
        bot=bot,
        openai_client=openai_client,
        admin_service=admin_service,
        debounce_manager=debounce_manager,
        config=cfg,
    )

    message.answer_guest_query.assert_called_once()
    # Support both positional and keyword invocation in the handler
    call = message.answer_guest_query.call_args
    result = call.kwargs.get("result") or (call.args[0] if call.args else None)
    assert isinstance(result, InlineQueryResultArticle)
    assert isinstance(result.input_message_content, InputTextMessageContent)
    assert result.input_message_content.message_text == "Hello, world!"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_handler_skips_message_without_guest_query_id():
    """
    Defensive guard: if aiogram somehow routed an update without
    ``guest_query_id``, calling ``answer_guest_query`` on it would explode.
    The handler must bail out early without touching OpenAI.
    """
    cfg = _make_config()
    router = create_guest_router(cfg)
    handler = _extract_handler(router)

    message = _make_message(guest_query_id=None)
    bot = _make_bot()
    openai_client = _make_openai_client()
    admin_service = _make_admin_service()
    debounce_manager = _make_debounce_manager()

    await handler(
        message=message,
        bot=bot,
        openai_client=openai_client,
        admin_service=admin_service,
        debounce_manager=debounce_manager,
        config=cfg,
    )

    openai_client.answer_question_simple.assert_not_awaited()
    message.answer_guest_query.assert_not_called()


# --------------------------------------------------------------------------- #
# Regression: photo + mention in caption (not text) must trigger vision       #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.unit
async def test_handler_handles_photo_with_mention_in_caption():
    """
    Regression for the parallel bug we fixed in message_router: when a user
    attaches a photo and writes "@bot what's this?" in the caption,
    Telegram populates ``message.caption`` (not ``message.text``). The
    guest handler must:
    
    1. Pull the question from caption, not text.
    2. Strip the ``@bot`` mention from it.
    3. Run vision on the attached photo.
    4. Reply with the model's answer.
    """
    cfg = _make_config()
    router = create_guest_router(cfg)
    handler = _extract_handler(router)

    photo = _make_photo()
    message = _make_message(
        text=None,
        caption="@mybot what's this?",
        photo=[photo],
    )
    bot = _make_bot(username="mybot")
    openai_client = _make_openai_client(
        vision_enabled=True,
        answer="It's a cat.",
        describe_image_result="A tabby cat.",
    )
    admin_service = _make_admin_service()
    debounce_manager = _make_debounce_manager()

    async def fake_download(_photo, destination):
        destination.write(b"\x00")
    message.bot.download = AsyncMock(side_effect=fake_download)

    await handler(
        message=message,
        bot=bot,
        openai_client=openai_client,
        admin_service=admin_service,
        debounce_manager=debounce_manager,
        config=cfg,
    )

    # Vision actually ran on the photo
    openai_client.describe_image.assert_awaited_once()

    # The prompt sent to the text model contains the cleaned caption
    # (no @mention) AND the image description.
    asked_question = openai_client.answer_question_simple.call_args.args[0]
    assert "@mybot" not in asked_question
    assert "what's this?" in asked_question
    assert "A tabby cat." in asked_question

    # And a reply was produced for the single guest-answer slot.
    message.answer_guest_query.assert_called_once()


# --------------------------------------------------------------------------- #
# Regression: replied-to text must be forwarded as context                    #
# --------------------------------------------------------------------------- #


def _make_replied_text(
    text: str,
    *,
    username: Optional[str] = "alice",
    first_name: Optional[str] = None,
):
    """Build a Message-like stub to place into ``message.reply_to_message``."""
    replied = MagicMock()
    replied.text = text
    replied.caption = None
    replied.photo = []
    from_user = MagicMock()
    from_user.username = username
    from_user.first_name = first_name
    replied.from_user = from_user
    return replied


@pytest.mark.asyncio
@pytest.mark.unit
async def test_handler_forwards_replied_text_into_prompt():
    """
    Regression for reported bug: when a guest message is a reply to a
    text-only post (no photo), the original text of that post was being
    dropped. Now it must be embedded into the prompt so the model has the
    anchor the user was asking about.
    """
    cfg = _make_config()
    router = create_guest_router(cfg)
    handler = _extract_handler(router)

    replied = _make_replied_text(
        "The mitochondria is the powerhouse of the cell.",
        username="alice",
    )
    message = _make_message(
        text="@mybot is that even true?",
        reply_to_message=replied,
    )
    bot = _make_bot(username="mybot")
    openai_client = _make_openai_client(answer="Yes, roughly.")
    admin_service = _make_admin_service()
    debounce_manager = _make_debounce_manager()

    await handler(
        message=message,
        bot=bot,
        openai_client=openai_client,
        admin_service=admin_service,
        debounce_manager=debounce_manager,
        config=cfg,
    )

    prompt = openai_client.answer_question_simple.call_args.args[0]
    assert "mitochondria" in prompt
    assert "@alice" in prompt
    assert "is that even true?" in prompt


@pytest.mark.asyncio
@pytest.mark.unit
async def test_handler_forwards_replied_text_without_username():
    """
    If the replied-to user has neither a username nor a first_name, the
    quote should still be attached without an empty ``@:`` prefix.
    """
    cfg = _make_config()
    router = create_guest_router(cfg)
    handler = _extract_handler(router)

    replied = _make_replied_text(
        "anonymous wisdom",
        username=None,
        first_name=None,
    )
    message = _make_message(
        text="@mybot explain",
        reply_to_message=replied,
    )
    bot = _make_bot(username="mybot")
    openai_client = _make_openai_client(answer="ok")
    admin_service = _make_admin_service()
    debounce_manager = _make_debounce_manager()

    await handler(
        message=message,
        bot=bot,
        openai_client=openai_client,
        admin_service=admin_service,
        debounce_manager=debounce_manager,
        config=cfg,
    )

    prompt = openai_client.answer_question_simple.call_args.args[0]
    assert "anonymous wisdom" in prompt
    # No stray "@:" marker when we had no author to attribute.
    assert "@:" not in prompt


@pytest.mark.asyncio
@pytest.mark.unit
async def test_handler_combines_reply_text_and_image_description():
    """
    When replying to a text post AND attaching a photo of your own, the
    prompt should contain *both* the quoted text and the image description.
    """
    cfg = _make_config()
    router = create_guest_router(cfg)
    handler = _extract_handler(router)

    replied = _make_replied_text("I found this yesterday:", username="bob")
    photo = _make_photo()
    message = _make_message(
        text="@mybot is it a threat?",
        photo=[photo],
        reply_to_message=replied,
    )
    bot = _make_bot(username="mybot")
    openai_client = _make_openai_client(
        vision_enabled=True,
        answer="Probably a harmless mushroom.",
        describe_image_result="A red mushroom with white spots.",
    )
    admin_service = _make_admin_service()
    debounce_manager = _make_debounce_manager()

    async def fake_download(_photo, destination):
        destination.write(b"\x00")
    message.bot.download = AsyncMock(side_effect=fake_download)

    await handler(
        message=message,
        bot=bot,
        openai_client=openai_client,
        admin_service=admin_service,
        debounce_manager=debounce_manager,
        config=cfg,
    )

    prompt = openai_client.answer_question_simple.call_args.args[0]
    assert "I found this yesterday" in prompt
    assert "A red mushroom with white spots." in prompt
    assert "is it a threat?" in prompt
