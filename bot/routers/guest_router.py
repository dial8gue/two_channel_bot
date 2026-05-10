"""
Router for handling Telegram Guest Mode queries (Bot API 10.0 / aiogram 3.28+).

Guest Mode allows bots enabled in @BotFather's MiniApp ("Guest Mode" setting)
to receive and reply to a single message when they are mentioned or replied to
in any chat — even chats where the bot is not a member.

Key aiogram 3.28 primitives used:
- Observer: ``Router.guest_message``
- Shortcut: ``Message.answer_guest_query(...)``
- Fields on Message: ``guest_query_id``, ``guest_bot_caller_user``,
  ``guest_bot_caller_chat``

Constraints imposed by the Telegram API (not ours):
- The bot may issue at most ONE reply per guest query.
- Regular ``message.answer(...)`` / ``message.reply(...)`` will fail here
  ("bot is not a member of the chat"); use ``answer_guest_query`` instead.
- The bot has NO access to chat history or participant list.
"""

import logging
import re
import uuid
from io import BytesIO
from typing import Optional

from aiogram import Router, Bot
from aiogram.types import (
    InlineQueryResultArticle,
    InputTextMessageContent,
    Message,
)

from config.settings import Config
from openai_client.client import OpenAIClient, OpenAIClientError
from services.admin_service import AdminService
from utils.debounce_manager import DebounceManager
from utils.message_formatter import MessageFormatter


logger = logging.getLogger(__name__)


# Global cache for bot username (stable for the lifetime of the process)
_bot_username: str = ""


async def _get_bot_username(bot: Bot) -> str:
    """Return (and cache) the bot's @username."""
    global _bot_username
    if not _bot_username:
        me = await bot.get_me()
        _bot_username = me.username or ""
    return _bot_username


def _strip_bot_mention(text: str, bot_username: str) -> str:
    """Remove leading/trailing ``@botname`` mention from text."""
    if not text or not bot_username:
        return text
    pattern = rf"@{re.escape(bot_username)}\b"
    return re.sub(pattern, "", text, flags=re.IGNORECASE).strip()


async def _describe_image_if_any(
    message: Message, openai_client: OpenAIClient
) -> Optional[str]:
    """
    Download and describe an image attached to the guest query or to the
    replied message. Returns description text or None.
    """
    if not openai_client.vision_enabled:
        return None

    photo_message: Optional[Message] = None
    if message.photo:
        photo_message = message
    elif message.reply_to_message and message.reply_to_message.photo:
        photo_message = message.reply_to_message

    if not photo_message:
        return None

    try:
        photo = photo_message.photo[-1]
        logger.info(
            "Downloading guest-query image for vision",
            extra={
                "file_id": photo.file_id,
                "width": photo.width,
                "height": photo.height,
            },
        )
        buf = BytesIO()
        await message.bot.download(photo, destination=buf)
        return await openai_client.describe_image(buf.getvalue())
    except OpenAIClientError as e:
        logger.warning(f"Guest: failed to describe image: {e}")
        return None
    except Exception as e:
        logger.error(f"Guest: unexpected error while describing image: {e}", exc_info=True)
        return None


async def _resolve_guest_debounce(
    admin_service: AdminService, config: Config
) -> int:
    """Return the current per-user guest debounce interval in seconds."""
    override = await admin_service.get_guest_debounce_seconds()
    if override is not None and override > 0:
        return override
    return config.guest_debounce_seconds


async def _resolve_guest_mode_enabled(
    admin_service: AdminService, config: Config
) -> bool:
    """Return whether the guest handler should answer queries right now."""
    override = await admin_service.is_guest_mode_enabled()
    if override is None:
        return config.guest_mode_enabled
    return override


async def _safe_answer_guest(message: Message, text: str) -> None:
    """
    Reply to a guest query with three-tier formatting fallback
    (Markdown → HTML → plain text).

    Bot API 10.0 requires the reply to be wrapped in an ``InlineQueryResult``
    (the same primitive used for inline mode), so we build an
    ``InlineQueryResultArticle`` with ``InputTextMessageContent``.
    
    Note: Bot-level ``link_preview_is_disabled`` does NOT propagate into
    ``InputTextMessageContent``, because the content is sent by Telegram
    on the bot's behalf rather than via a Bot API method. So we set the
    flag explicitly here to keep guest replies consistent with regular
    replies.
    """

    def _build(parse_mode: Optional[str], body: str) -> InlineQueryResultArticle:
        # Telegram requires a unique id + title per article even though the
        # user never sees the article metadata — only the message body.
        return InlineQueryResultArticle(
            id=uuid.uuid4().hex,
            title="Answer",
            input_message_content=InputTextMessageContent(
                message_text=body,
                parse_mode=parse_mode,
                disable_web_page_preview=True,
            ),
        )

    try:
        await message.answer_guest_query(result=_build("Markdown", text))
        return
    except Exception as md_err:
        logger.warning(f"Guest: markdown failed, falling back to HTML: {md_err}")

    try:
        html_text = MessageFormatter.convert_to_html(text)
        await message.answer_guest_query(result=_build("HTML", html_text))
        return
    except Exception as html_err:
        logger.warning(f"Guest: HTML failed, falling back to plain: {html_err}")

    plain = MessageFormatter.strip_formatting(text)
    await message.answer_guest_query(result=_build(None, plain))


def create_guest_router(config: Config) -> Router:
    """
    Create and configure the guest_message router.
    
    Args:
        config: Bot configuration (used for fallback defaults)
    
    Returns:
        Configured Router instance.
    """
    router = Router(name="guest_router")

    @router.guest_message()
    async def on_guest_message(
        message: Message,
        bot: Bot,
        openai_client: OpenAIClient,
        admin_service: AdminService,
        debounce_manager: DebounceManager,
        config: Config,
    ) -> None:
        """
        Handle a single Guest Mode query.
        
        Protocol:
        1. Bail out quickly if Guest Mode is toggled off in admin settings.
        2. Apply per-user debounce (key ``guest:<user_id>``) to throttle abuse.
        3. Strip the bot's mention from incoming text.
        4. If there's an image (in this message or in reply) and vision is on,
           describe it and append to the question.
        5. Call ``openai_client.answer_question_simple`` — guests don't have
           chat history context anyway.
        6. Reply via ``message.answer_guest_query``. Regular reply/answer
           would fail because the bot is not a chat member.
        """
        try:
            # Basic shape check: aiogram wouldn't route here without a guest query,
            # but we still guard against exotic payloads.
            if not getattr(message, "guest_query_id", None):
                logger.warning("guest_message without guest_query_id — skipping")
                return

            # ``guest_bot_caller_user`` / ``guest_bot_caller_chat`` are only
            # populated on messages **sent by** a guest bot (so other bots can
            # see whom it served). On **incoming** guest_message updates, the
            # author is the regular ``from_user`` and the venue is ``chat``.
            # Fall back to the caller_* fields only for defensive parity.
            caller_user = message.from_user or message.guest_bot_caller_user
            caller_chat = message.chat or message.guest_bot_caller_chat
            user_id = caller_user.id if caller_user else None
            chat_id = caller_chat.id if caller_chat else None
            is_admin = user_id is not None and user_id == config.admin_id

            logger.info(
                "Guest query received",
                extra={
                    "guest_query_id": message.guest_query_id,
                    "user_id": user_id,
                    "chat_id": chat_id,
                    "is_admin": is_admin,
                    "has_photo": bool(message.photo),
                    "has_reply": bool(message.reply_to_message),
                },
            )

            # 1) Feature toggle
            if not await _resolve_guest_mode_enabled(admin_service, config):
                logger.info(
                    "Guest mode disabled, ignoring query",
                    extra={"user_id": user_id},
                )
                return

            # 2) Per-user debounce. Admin bypasses it for parity with /ask:
            # operator should be able to test the bot without hitting their
            # own rate limit.
            if user_id is not None and not is_admin:
                debounce_interval = await _resolve_guest_debounce(admin_service, config)
                operation_key = f"guest:{user_id}"
                can_run, remaining = await debounce_manager.can_execute(
                    operation_key, debounce_interval
                )
                if not can_run:
                    logger.info(
                        "Guest query throttled by debounce",
                        extra={
                            "user_id": user_id,
                            "remaining_seconds": remaining,
                            "interval": debounce_interval,
                        },
                    )
                    # Each guest query has its own independent reply slot,
                    # so spending this one on a throttling notice doesn't
                    # cost the user their "real" answer — they'll get a
                    # fresh slot on their next message.
                    warning = MessageFormatter.format_debounce_warning(
                        "задавал вопрос", remaining
                    )
                    await _safe_answer_guest(message, warning)
                    return

            # 3) Build the prompt
            raw_text = (message.text or message.caption or "").strip()
            bot_username = await _get_bot_username(bot)
            question = _strip_bot_mention(raw_text, bot_username)

            # If user replied to a bot message with only a photo / sticker,
            # fall back to a sensible default prompt.
            if not question and (message.photo or message.sticker or message.animation):
                question = "Что на этом изображении?"

            if not question:
                logger.info(
                    "Guest query has no question text, skipping",
                    extra={"user_id": user_id},
                )
                return

            # 4) Optional image description (vision).
            #    Works for photos in the current message *and* in the
            #    replied-to message.
            image_description = await _describe_image_if_any(message, openai_client)

            # 5) Extract the text of the replied-to message, if any.
            #    Telegram includes reply_to_message in guest_message updates
            #    exactly so the bot can use it as context. Without this,
            #    "@bot what does X mean by this?" replying to a text post
            #    would reach the model as just "what does X mean by this?",
            #    losing the anchor message entirely.
            reply_context: Optional[str] = None
            reply = message.reply_to_message
            if reply is not None:
                reply_text = (reply.text or reply.caption or "").strip()
                if reply_text:
                    reply_author = ""
                    if reply.from_user:
                        reply_author = (
                            reply.from_user.username
                            or reply.from_user.first_name
                            or ""
                        )
                    reply_context = (
                        f"@{reply_author}: {reply_text}"
                        if reply_author
                        else reply_text
                    )

            # 6) Stitch everything the model should see into one prompt.
            #    ``answer_question_simple`` has no structured context slot,
            #    so we prepend the reply quote and/or image description in
            #    human-readable form.
            prompt_parts = []
            if reply_context:
                prompt_parts.append(f"[Цитата: {reply_context}]")
            if image_description:
                prompt_parts.append(f"[Изображение: {image_description}]")
            prompt_parts.append(question)
            full_question = "\n\n".join(prompt_parts)

            # 7) Ask the model. Guest mode has no chat history, so use the
            # "simple" codepath that doesn't require MessageModel context.
            answer = await openai_client.answer_question_simple(full_question)

            # 8) Reply via the dedicated guest method.
            await _safe_answer_guest(message, answer)

            # Mark as executed only after a successful reply so failed attempts
            # don't consume the user's debounce budget. Admin is exempt for
            # parity with the rest of the debounce logic above.
            if user_id is not None and not is_admin:
                try:
                    await debounce_manager.mark_executed(f"guest:{user_id}")
                except Exception as mark_err:
                    logger.warning(
                        f"Guest: failed to mark debounce executed: {mark_err}"
                    )

            logger.info(
                "Guest query answered",
                extra={
                    "user_id": user_id,
                    "chat_id": chat_id,
                    "answer_length": len(answer) if answer else 0,
                },
            )

        except OpenAIClientError as e:
            logger.error(
                f"Guest: OpenAI error: {e}",
                extra={"guest_query_id": getattr(message, "guest_query_id", None)},
                exc_info=True,
            )
            # Best effort: try to inform the user in the guest reply slot.
            try:
                await _safe_answer_guest(
                    message, f"⚠️ Не удалось обработать запрос: {e}"
                )
            except Exception:
                pass
        except Exception as e:
            logger.error(
                f"Guest: unexpected error while handling guest_message: {e}",
                extra={"guest_query_id": getattr(message, "guest_query_id", None)},
                exc_info=True,
            )
            try:
                await _safe_answer_guest(
                    message, "❌ Произошла ошибка при обработке запроса."
                )
            except Exception:
                pass

    return router
