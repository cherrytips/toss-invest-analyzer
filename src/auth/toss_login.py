"""
토스증권 로그인 모듈
- Playwright 기반 브라우저 자동화
- 세션 쿠키 저장/복원으로 재로그인 최소화
- OTP 단계는 브라우저에서 직접 수행 (사용자 상호작용 필요)
"""

import json
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright, Browser, Page
from rich.console import Console
from rich.prompt import Prompt

console = Console()

TOSS_URL = "https://www.tossinvest.com"
LOGIN_SELECTORS = [
    "button:has-text('로그인')",
    "[data-testid='login-button']",
    "a:has-text('로그인')",
    ".login-button",
]

LOGGED_IN_SELECTORS = [
    "[data-testid='user-profile']",
    "[class*='UserMenu']",
    "[class*='userProfile']",
    "[class*='myPage']",
    "button:has-text('내 자산')",
    "a:has-text('내 자산')",
]

PHONE_INPUT_SELECTORS = [
    "input[type='tel']",
    "input[placeholder*='전화번호']",
    "input[placeholder*='휴대폰']",
    "input[placeholder*='휴대전화']",
    "input[name='phone']",
]


class TossLogin:
    def __init__(self, config):
        self.config = config
        self.cookies_path = config.cache_dir / "toss_session.json"

    async def login(self) -> tuple[Page | None, object | None]:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=self.config.headless,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="ko-KR",
            timezone_id="Asia/Seoul",
        )

        # 저장된 세션 쿠키 로드 시도
        if self.cookies_path.exists():
            try:
                cookies = json.loads(self.cookies_path.read_text(encoding="utf-8"))
                await context.add_cookies(cookies)
                console.print("[dim]이전 세션 쿠키 로드 완료[/dim]")
            except Exception:
                pass

        page = await context.new_page()

        try:
            console.print(f"[dim]토스증권 접속 중: {TOSS_URL}[/dim]")
            await page.goto(TOSS_URL, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)

            # 로그인 상태 확인
            if await self._is_logged_in(page):
                console.print("[green]✓ 기존 세션으로 로그인 유지됨[/green]")
                await self._save_cookies(context)
                return page, browser

            # 로그인 필요
            console.print("[yellow]로그인이 필요합니다.[/yellow]")
            await self._perform_login(page, context)

            if await self._is_logged_in(page):
                console.print("[green]✓ 로그인 성공[/green]")
                await self._save_cookies(context)
                return page, browser
            else:
                console.print("[red]로그인 상태를 확인할 수 없습니다.[/red]")
                console.print("[dim]브라우저를 열어두고 수동으로 확인해주세요.[/dim]")
                input("로그인 완료 후 Enter를 눌러주세요...")
                await self._save_cookies(context)
                return page, browser

        except Exception as e:
            console.print(f"[red]로그인 중 오류: {e}[/red]")
            await browser.close()
            return None, None

    async def _is_logged_in(self, page: Page) -> bool:
        for selector in LOGGED_IN_SELECTORS:
            try:
                await page.wait_for_selector(selector, timeout=2000)
                return True
            except Exception:
                pass
        return False

    async def _perform_login(self, page: Page, context):
        # 로그인 버튼 클릭 시도
        login_clicked = False
        for selector in LOGIN_SELECTORS:
            try:
                await page.click(selector, timeout=3000)
                login_clicked = True
                console.print(f"[dim]로그인 버튼 클릭: {selector}[/dim]")
                await page.wait_for_timeout(1500)
                break
            except Exception:
                pass

        if not login_clicked:
            console.print("[yellow]로그인 버튼을 찾지 못했습니다. 직접 클릭해주세요.[/yellow]")

        # 전화번호 자동 입력 시도
        phone_number = self.config.user_phone.replace("-", "").replace(" ", "")
        phone_filled = False
        for selector in PHONE_INPUT_SELECTORS:
            try:
                await page.wait_for_selector(selector, timeout=3000)
                await page.fill(selector, phone_number)
                phone_filled = True
                console.print(f"[green]✓ 전화번호 자동 입력: {self.config.user_phone}[/green]")
                await page.wait_for_timeout(500)
                await page.keyboard.press("Enter")
                break
            except Exception:
                pass

        if not phone_filled:
            console.print(f"[yellow]전화번호 입력 필드를 찾지 못했습니다.[/yellow]")
            console.print(f"[bold]전화번호: {self.config.user_phone}[/bold] 를 직접 입력해주세요.")

        console.print()
        console.print("[bold cyan]═══════════════════════════════════════[/bold cyan]")
        console.print("[bold yellow]  브라우저에서 로그인을 완료해주세요.[/bold yellow]")
        console.print("[dim]  (SMS 인증번호 입력 등 나머지 단계를 진행해주세요)[/dim]")
        console.print("[bold cyan]═══════════════════════════════════════[/bold cyan]")
        console.print()
        input("  로그인 완료 후 Enter를 눌러주세요... ")

        await page.wait_for_timeout(2000)

    async def _save_cookies(self, context):
        try:
            cookies = await context.cookies()
            self.cookies_path.write_text(
                json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            console.print("[dim]세션 정보 저장 완료[/dim]")
        except Exception as e:
            console.print(f"[dim]세션 저장 실패: {e}[/dim]")

    def clear_session(self):
        """저장된 세션 삭제 (재로그인 필요 시 사용)"""
        if self.cookies_path.exists():
            self.cookies_path.unlink()
            console.print("[yellow]세션이 초기화되었습니다. 다시 로그인해주세요.[/yellow]")
