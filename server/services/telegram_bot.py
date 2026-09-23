from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from sqlmodel import Session, select

from server.core.config import Settings
from server.core.database import engine
from server.models.portfolio import AiReport
from server.models.user import User
from server.services.portfolio_service import get_portfolio_summary, list_market_news

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"


class TelegramBot:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._task: asyncio.Task | None = None
        self._offset = 0
        self._stop = asyncio.Event()

    @property
    def enabled(self) -> bool:
        return bool(self.settings.telegram_bot_token.strip() and self.settings.telegram_chat_id.strip())

    async def start(self) -> None:
        if not self.enabled:
            logger.info("Telegram bot disabled (missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID).")
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._poll_loop(), name="telegram-bot")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _poll_loop(self) -> None:
        token = self.settings.telegram_bot_token
        url = f"{TELEGRAM_API}/bot{token}/getUpdates"
        async with httpx.AsyncClient(timeout=40.0) as client:
            while not self._stop.is_set():
                try:
                    response = await client.get(
                        url,
                        params={"timeout": 25, "offset": self._offset},
                    )
                    response.raise_for_status()
                    payload = response.json()
                    for update in payload.get("result", []):
                        self._offset = max(self._offset, int(update.get("update_id", 0)) + 1)
                        await self._handle_update(client, update)
                except asyncio.CancelledError:
                    raise
                except Exception:  # noqa: BLE001
                    logger.exception("Telegram polling error")
                    await asyncio.sleep(3)

    async def _handle_update(self, client: httpx.AsyncClient, update: dict[str, Any]) -> None:
        message = update.get("message") or update.get("edited_message")
        if not message:
            return
        chat = message.get("chat") or {}
        chat_id = str(chat.get("id", ""))
        if chat_id != str(self.settings.telegram_chat_id).strip():
            return

        text = (message.get("text") or "").strip()
        if not text:
            return

        command = text.split()[0].split("@")[0].lower()
        reply = await asyncio.to_thread(self._build_reply, command)
        await client.post(
            f"{TELEGRAM_API}/bot{self.settings.telegram_bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": reply},
        )

    def _resolve_user(self, session: Session) -> User | None:
        email = self.settings.telegram_user_email.strip().lower()
        if not email:
            return None
        return session.exec(select(User).where(User.email == email, User.is_deleted == False)).first()  # noqa: E712

    def _build_reply(self, command: str) -> str:
        with Session(engine) as session:
            user = self._resolve_user(session)
            if user is None:
                return "TELEGRAM_USER_EMAIL yapılandırılmamış veya kullanıcı bulunamadı."

            if command == "/portfolio":
                summary = get_portfolio_summary(session, user.id)
                lines = [
                    "Portföy özeti",
                    f"Toplam değer: {summary['totalValue']:.2f} TRY",
                    f"Toplam maliyet: {summary['totalCost']:.2f} TRY",
                    f"Kâr/Zarar: {summary['profitLoss']:.2f} TRY ({summary['profitLossPercentage']:.2f}%)",
                    "",
                ]
                for holding in summary["holdings"][:15]:
                    lines.append(
                        f"- {holding['symbol']}: {holding['sharesCount']} lot @ "
                        f"{holding['currentPrice']:.2f} → {holding['profitLoss']:.2f}"
                    )
                if not summary["holdings"]:
                    lines.append("Portföy boş.")
                return "\n".join(lines)

            if command == "/analiz":
                report = session.exec(
                    select(AiReport)
                    .where(AiReport.user_id == user.id, AiReport.is_deleted == False)  # noqa: E712
                    .order_by(AiReport.created_at_utc.desc())
                ).first()
                if report is None:
                    return "Rapor yok. Önce uygulamadan analiz üret."
                summary = report.executive_summary.strip() or report.title
                return f"{report.title}\nRisk: {report.risk_score}/10\n\n{summary[:3500]}"

            if command == "/haber":
                news = list_market_news(session, limit=8)
                if not news:
                    return "Haber bulunamadı."
                lines = ["Son haberler"]
                for item in news[:8]:
                    lines.append(f"- [{item['sentiment']}] {item['symbol']}: {item['title']}")
                return "\n".join(lines)

            return "Komutlar: /portfolio /analiz /haber"
