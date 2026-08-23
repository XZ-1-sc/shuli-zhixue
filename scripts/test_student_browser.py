"""Dual-viewport browser regression for the student portal with a temporary account."""

from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from sqlalchemy import text


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.database.session import SessionLocal  # noqa: E402
from app.utils.password import hash_password  # noqa: E402


BASE_URL = "http://localhost:8080"
OUTPUT_DIR = ROOT / "tmp" / "student-browser"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def create_student() -> tuple[int, str, str]:
    marker = f"{int(time.time())}_{uuid.uuid4().hex[:6]}"
    username = f"qa_student_layout_{marker}"
    password = f"QaStudent-{marker}-Aa9!"
    with SessionLocal() as db:
        result = db.execute(
            text(
                "INSERT INTO users (username,password_hash,nickname,role,current_stage,status) "
                "VALUES (:username,:password_hash,:username,'student','大一',1)"
            ),
            {"username": username, "password_hash": hash_password(password)},
        )
        user_id = int(result.lastrowid)
        db.commit()
    return user_id, username, password


def wait_for_vue(driver: webdriver.Edge, wait: WebDriverWait) -> None:
    wait.until(lambda current: current.execute_script("return document.readyState") == "complete")
    wait.until(lambda current: len(current.find_elements(By.CSS_SELECTOR, "#app > *")) > 0)
    time.sleep(0.45)


def assert_healthy(driver: webdriver.Edge, heading: str) -> None:
    body = driver.find_element(By.TAG_NAME, "body").text
    assert heading in body, f"Page heading missing: {heading}"
    dimensions = driver.execute_script(
        "return {viewport: innerWidth, width: document.documentElement.scrollWidth};"
    )
    if dimensions["width"] > dimensions["viewport"] + 4:
        offenders = driver.execute_script(
            """
            return [...document.querySelectorAll('body *')]
              .map((element) => {
                const rect = element.getBoundingClientRect();
                return {tag: element.tagName, className: typeof element.className === 'string' ? element.className : '', left: Math.round(rect.left), right: Math.round(rect.right), width: Math.round(rect.width)};
              })
              .filter((item) => item.right > innerWidth + 4 || item.left < -4)
              .slice(0, 20);
            """
        )
        raise AssertionError({"dimensions": dimensions, "offenders": offenders})


def assert_no_browser_errors(driver: webdriver.Edge, viewport: str, path: str) -> None:
    errors = [entry for entry in driver.get_log("browser") if entry.get("level") == "SEVERE"]
    assert not errors, {"viewport": viewport, "path": path, "errors": errors}


def assert_chart_fills_host(driver: webdriver.Edge, viewport: str) -> None:
    sizes = driver.execute_script(
        """
        const host = document.querySelector('.graph-canvas');
        const canvas = host?.querySelector('canvas');
        if (!host || !canvas) return null;
        const hostRect = host.getBoundingClientRect();
        const canvasRect = canvas.getBoundingClientRect();
        return {hostWidth: hostRect.width, hostHeight: hostRect.height, canvasWidth: canvasRect.width, canvasHeight: canvasRect.height};
        """
    )
    assert sizes, {"viewport": viewport, "reason": "knowledge graph canvas missing"}
    assert abs(sizes["hostWidth"] - sizes["canvasWidth"]) <= 4, {"viewport": viewport, "sizes": sizes}
    assert abs(sizes["hostHeight"] - sizes["canvasHeight"]) <= 4, {"viewport": viewport, "sizes": sizes}


def main() -> None:
    user_id, username, password = create_student()
    options = Options()
    options.binary_location = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1440,1000")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-first-run")
    options.add_argument("--disable-features=msEdgeSidebarV2")
    options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
    driver: webdriver.Edge | None = None
    pages = [
        ("/", "大学数学学习中控台", "dashboard"),
        ("/roadmap", "完整学习规划", "roadmap"),
        ("/knowledge", "知识图谱与错题复盘", "knowledge"),
        ("/practice", "做题训练", "practice"),
        ("/review", "按错因回炉", "review"),
        ("/messages", "学习提醒与系统通知", "messages"),
        ("/assignments", "我的作业", "assignments"),
    ]
    try:
        driver = webdriver.Edge(options=options)
        driver.set_page_load_timeout(35)
        wait = WebDriverWait(driver, 25)
        driver.get(f"{BASE_URL}/auth?role=student&mode=login")
        wait_for_vue(driver, wait)
        driver.find_element(By.CSS_SELECTOR, "input[autocomplete='username']").send_keys(username)
        driver.find_element(By.CSS_SELECTOR, "input[autocomplete='current-password']").send_keys(password)
        driver.find_element(By.CSS_SELECTOR, ".identity-submit").click()
        wait.until(lambda current: current.current_url.rstrip("/") == BASE_URL)

        for path, heading, name in pages:
            driver.get(f"{BASE_URL}{path}")
            wait_for_vue(driver, wait)
            assert_healthy(driver, heading)
            driver.save_screenshot(str(OUTPUT_DIR / f"desktop-{name}.png"))
            if name == "knowledge":
                assert_chart_fills_host(driver, "desktop")
            assert_no_browser_errors(driver, "desktop", path)

        driver.set_window_size(390, 844)
        driver.execute_cdp_cmd(
            "Emulation.setDeviceMetricsOverride",
            {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True},
        )
        for path, heading, name in pages:
            driver.get(f"{BASE_URL}{path}")
            wait_for_vue(driver, wait)
            assert_healthy(driver, heading)
            driver.save_screenshot(str(OUTPUT_DIR / f"mobile-{name}.png"))
            if name == "knowledge":
                assert_chart_fills_host(driver, "mobile")
            assert_no_browser_errors(driver, "mobile", path)
        print(f"STUDENT_BROWSER_OK screenshots={OUTPUT_DIR}")
    finally:
        if driver:
            driver.quit()
        with SessionLocal() as db:
            db.execute(text("DELETE FROM users WHERE id=:id"), {"id": user_id})
            db.commit()


if __name__ == "__main__":
    main()
