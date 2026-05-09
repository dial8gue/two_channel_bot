"""
Unit tests for bot.routers.message_router.

These tests exercise ``handle_group_message`` directly, because the bug
we guard against (photos with a bot mention in the caption getting
silently dropped before reaching ask_router) lived in that handler's
own text-extraction logic, independent of the dispatcher.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.enums import ChatType

from bot.routers.message_router import router as message_router


def _extract_handler():
    """Return the concrete callback registered for ``message`` updates."""
    handlers = message_router.message.handlers
    assert handlers, "message_router must register message handlers"
    # The first handler is handle_group_message; later ones (if any) are
    # different observers (edited_message, my_chat_member) and not in this list.
    return handlers[0].callback


def _make_message(
    *,
    text=None,
    caption=None,
    photo=None,
    sticker=None,
    animation=None,
    user_id: int = 7,
    username: str = "user",
    chat_id: int = -100123,
    chat_title: str = "Test Group",
):
    """Build a Message-like stub for handle_group_message."""
    message = MagicMock()
    message.text = text
    message.caption = caption
    message.photo = photo or []
    message.sticker = sticker
    message.animation = animation
    message.reply_to_message = None

    from_user = MagicMock()
    from_user.id = user_id
    from_user.username = username
    from_user.first_name = username
    from_user.is_bot = False
    message.from_user = from_user

    chat = MagicMock()
    chat.id = chat_id
    chat.title = chat_title
    chat.type = ChatType.SUPERGROUP
    message.chat = chat

    message.message_id = 42
    message.date = datetime(2026, 5, 9, 12, 0, 0)

    bot = AsyncMock()
    bot.id = 1
    message.bot = bot
    return message


def _make_admin_service():
    """AdminService stub: pretend the group is already registered."""
    svc = MagicMock()
    group = MagicMock()
    group.title = "Test Group"
    svc.group_repository = MagicMock()
    svc.group_repository.get = AsyncMock(return_value=group)
    svc.add_or_update_group = AsyncMock()
    return svc


def _make_message_service():
    svc = MagicMock()
    svc.save_message = AsyncMock()
    svc.cleanup_old_messages = AsyncMock()
    return svc


# --------------------------------------------------------------------------- #
# Regression: photo + caption with bot mention must NOT be dropped            #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.unit
async def test_photo_with_caption_is_saved_and_defers_to_downstream():
    """
    Regression for bug: when a user attaches a photo and writes "@bot what's
    this?" in the caption, handle_group_message used to look only at
    message.text, see None, and silently ``return`` without SkipHandler.
    That killed the update before ask_router could react to the mention,
    so vision never ran.
    
    Expected behavior now: the caption is used as the text payload, the
    message is persisted, and SkipHandler is raised to let ask_router take
    over.
    """
    handler = _extract_handler()

    photo = MagicMock()
    message = _make_message(
        text=None,
        caption="@mybot what's this?",
        photo=[photo],
    )
    admin_service = _make_admin_service()
    message_service = _make_message_service()

    with pytest.raises(SkipHandler):
        await handler(
            message=message,
            message_service=message_service,
            admin_service=admin_service,
        )

    message_service.save_message.assert_awaited_once()
    saved_kwargs = message_service.save_message.call_args.kwargs
    assert saved_kwargs["text"] == "@mybot what's this?"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_photo_without_caption_skips_forward_for_ask_router():
    """
    Photo without caption has no storable text, but the handler still must
    NOT swallow the update — otherwise ask_router can't react to a
    reply-to-bot on a pure-image message.
    """
    handler = _extract_handler()

    photo = MagicMock()
    message = _make_message(text=None, caption=None, photo=[photo])
    admin_service = _make_admin_service()
    message_service = _make_message_service()

    with pytest.raises(SkipHandler):
        await handler(
            message=message,
            message_service=message_service,
            admin_service=admin_service,
        )

    # Nothing to persist — we don't want blank rows in the DB.
    message_service.save_message.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_plain_text_message_is_saved_and_skips_to_downstream():
    """Baseline: plain text still persists and still defers to ask_router."""
    handler = _extract_handler()

    message = _make_message(text="hello there")
    admin_service = _make_admin_service()
    message_service = _make_message_service()

    with pytest.raises(SkipHandler):
        await handler(
            message=message,
            message_service=message_service,
            admin_service=admin_service,
        )

    message_service.save_message.assert_awaited_once()
    saved_kwargs = message_service.save_message.call_args.kwargs
    assert saved_kwargs["text"] == "hello there"
