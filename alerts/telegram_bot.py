"""
alerts/telegram_bot.py
Sends Telegram messages via python-telegram-bot (v20+).
Uses config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID.
"""

from __future__ import annotations

import asyncio
import logging

import config

logger = logging.getLogger(__name__)


async def _send_async(message: str) -> bool:
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.warning("Telegram credentials not configured")
        return False
    try:
        from telegram import Bot
        bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        await bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=message, parse_mode="HTML")
        return True
    except Exception as exc:
        logger.error("Telegram send failed: %s", exc)
        return False


def send_message(message: str) -> bool:
    """Synchronous wrapper — safe to call from Streamlit."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Streamlit runs an event loop; use a thread executor
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                fut = pool.submit(asyncio.run, _send_async(message))
                return fut.result(timeout=10)
        else:
            return loop.run_until_complete(_send_async(message))
    except Exception as exc:
        logger.error("send_message error: %s", exc)
        return False


def alert_signal_flip(label: str, score: float) -> bool:
    emoji = "🟢" if label == "Bullish" else ("🔴" if label == "Bearish" else "🟡")
    msg = (
        f"{emoji} <b>XAUUSD signal flipped to {label.upper()}</b>\n"
        f"Score: <b>{score:.1f}/100</b>"
    )
    return send_message(msg)


def alert_dfii10_breach(value: float, threshold: float, direction: str) -> bool:
    msg = (
        f"⚠️ <b>DFII10 crossed {direction} {threshold:.2f}%</b>\n"
        f"Current real yield: <b>{value:.2f}%</b>\n"
        f"{'📉 Bearish pressure on gold' if direction == 'above' else '📈 Supportive for gold'}"
    )
    return send_message(msg)


def alert_cot_change(mm_net: float, change: float) -> bool:
    arrow = "⬆️" if change > 0 else "⬇️"
    msg = (
        f"{arrow} <b>COT Managed Money net changed by {change:+,.0f} contracts</b>\n"
        f"Current net: <b>{mm_net:,.0f}</b>"
    )
    return send_message(msg)


def send_test_message() -> bool:
    return send_message("✅ <b>XAUUSD Research Platform</b> — Telegram alerts are working!")
