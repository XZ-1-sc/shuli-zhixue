"""Dual-viewport browser regression for the student portal with a temporary account."""

from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import InvalidArgumentException
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
        question_id = db.execute(
            text(
                "SELECT id FROM questions "
                "WHERE publish_status='published' AND deleted_at IS NULL "
                "ORDER BY id LIMIT 1"
            )
        ).scalar_one_or_none()
        if not question_id:
            raise AssertionError("浏览器回归需要至少一道已发布题目")
        db.execute(
            text(
                "INSERT INTO practice_records "
                "(task_id,user_id,question_id,selected_answer,is_correct,score,mistake_tags,time_spent_seconds,practice_mode) "
                "VALUES (:task_id,:user_id,:question_id,'QA',0,0.00,:mistake_tags,95,'assessment')"
            ),
            {
                "task_id": f"qa-browser-{marker}",
                "user_id": user_id,
                "question_id": int(question_id),
                "mistake_tags": json.dumps(["概念混淆"], ensure_ascii=False),
            },
        )
        db.commit()
    return user_id, username, password


def wait_for_vue(driver: webdriver.Edge, wait: WebDriverWait) -> None:
    wait.until(lambda current: current.execute_script("return document.readyState") == "complete")
    wait.until(lambda current: len(current.find_elements(By.CSS_SELECTOR, "#app > *")) > 0)
    time.sleep(0.45)


def assert_healthy(driver: webdriver.Edge, heading: str) -> None:
    body = driver.find_element(By.TAG_NAME, "body").text
    assert heading in body, f"Page heading missing: {heading}"
    forbidden = ["Internal Server Error", "服务器暂时无法处理请求", "加载失败"]
    assert not any(item in body for item in forbidden), body[:1200]
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


def assert_assistant_clear(driver: webdriver.Edge, viewport: str, path: str) -> None:
    collisions = driver.execute_script(
        """
        const orb = document.querySelector('.assistant-orb');
        if (!orb) return [{reason: 'assistant orb missing'}];
        const orbRect = orb.getBoundingClientRect();
        return [...document.querySelectorAll('a, button, input, select, textarea')]
          .filter((element) => element !== orb && !element.closest('.assistant-drawer'))
          .filter((element) => {
            const style = getComputedStyle(element);
            const rect = element.getBoundingClientRect();
            return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
          })
          .map((element) => {
            const rect = element.getBoundingClientRect();
            const overlapWidth = Math.min(orbRect.right, rect.right) - Math.max(orbRect.left, rect.left);
            const overlapHeight = Math.min(orbRect.bottom, rect.bottom) - Math.max(orbRect.top, rect.top);
            return {element, rect, overlapWidth, overlapHeight};
          })
          .filter((item) => item.overlapWidth > 1 && item.overlapHeight > 1)
          .map((item) => ({
            tag: item.element.tagName,
            className: typeof item.element.className === 'string' ? item.element.className : '',
            text: (item.element.textContent || item.element.value || '').trim().slice(0, 50),
            overlapWidth: Math.round(item.overlapWidth),
            overlapHeight: Math.round(item.overlapHeight)
          }));
        """
    )
    assert not collisions, {"viewport": viewport, "path": path, "collisions": collisions}


def assert_no_browser_errors(driver: webdriver.Edge, viewport: str, path: str) -> None:
    errors = [entry for entry in driver.get_log("browser") if entry.get("level") == "SEVERE"]
    assert not errors, {"viewport": viewport, "path": path, "errors": errors}


def collect_network_failures(driver: webdriver.Edge) -> list[dict[str, object]]:
    try:
        entries = driver.get_log("performance")
    except InvalidArgumentException:
        return []
    failures = []
    for entry in entries:
        message = json.loads(entry["message"])["message"]
        if message["method"] != "Network.responseReceived":
            continue
        response = message["params"]["response"]
        status = int(response["status"])
        url = str(response["url"])
        if status >= 400 and url.startswith(BASE_URL) and "/api/auth/me" not in url:
            failures.append({"status": status, "url": url})
    return failures


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


def assert_dashboard_containment(driver: webdriver.Edge, viewport: str) -> None:
    layout = driver.execute_script(
        """
        const inner = document.querySelector('.stage-inner');
        const stage = document.querySelector('.stage-progress-card');
        const daily = document.querySelector('.daily-practice-card');
        const primaryNav = document.querySelector('.student-primary-nav');
        const account = document.querySelector('.student-account-area');
        if (!inner || !stage || !daily) return null;
        const innerRect = inner.getBoundingClientRect();
        const escaped = [...inner.querySelectorAll('*')]
          .filter((element) => {
            const rect = element.getBoundingClientRect();
            return rect.width > 0 && (rect.left < innerRect.left - 2 || rect.right > innerRect.right + 2);
          })
          .map((element) => ({className: element.className || '', text: (element.textContent || '').trim().slice(0, 40)}))
          .slice(0, 10);
        return {
          innerClientWidth: inner.clientWidth,
          innerScrollWidth: inner.scrollWidth,
          stageRight: stage.getBoundingClientRect().right,
          dailyLeft: daily.getBoundingClientRect().left,
          sameRow: Math.abs(stage.getBoundingClientRect().top - daily.getBoundingClientRect().top) < 4,
          navRight: primaryNav?.getBoundingClientRect().right || 0,
          accountLeft: account?.getBoundingClientRect().left || innerWidth,
          escaped,
        };
        """
    )
    assert layout, {"viewport": viewport, "reason": "dashboard cards missing"}
    assert layout["innerScrollWidth"] <= layout["innerClientWidth"] + 2, {"viewport": viewport, "layout": layout}
    assert not layout["escaped"], {"viewport": viewport, "layout": layout}
    if layout["sameRow"]:
        assert layout["stageRight"] <= layout["dailyLeft"] + 1, {"viewport": viewport, "layout": layout}
    assert layout["navRight"] <= layout["accountLeft"] + 1, {"viewport": viewport, "layout": layout}


def main() -> None:
    user_id, username, password = create_student()
    options = Options()
    options.binary_location = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1440,1000")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-first-run")
    options.add_argument("--disable-features=msEdgeSidebarV2")
    options.set_capability("goog:loggingPrefs", {"browser": "ALL", "performance": "ALL"})
    driver: webdriver.Edge | None = None
    pages = [
        ("/", "大学数学学习中控台", "dashboard"),
        ("/roadmap", "完整学习规划", "roadmap"),
        ("/knowledge", "知识图谱与错题复盘", "knowledge"),
        ("/practice", "做题训练", "practice"),
        ("/review", "按错因回炉", "review"),
        ("/messages", "沟通与学习提醒", "messages"),
        ("/profile", "你的数学学习画像", "profile"),
        ("/achievements", "把进步留下痕迹", "achievements"),
        ("/resources", "课程讲义与练习入口", "resources"),
        ("/notebook", "记录定义、错因和证明思路", "notebook"),
        ("/settings", "调整你的学习目标", "settings"),
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
        assert driver.find_element(By.CSS_SELECTOR, ".assistant-orb").is_displayed()
        wait.until(
            lambda current: "当前账号还没有做题记录"
            not in current.find_element(By.TAG_NAME, "body").text
        )

        for path, heading, name in pages:
            driver.get(f"{BASE_URL}{path}")
            wait_for_vue(driver, wait)
            assert_healthy(driver, heading)
            assert driver.find_element(By.CSS_SELECTOR, ".assistant-orb").is_displayed()
            assert_assistant_clear(driver, "desktop", path)
            driver.save_screenshot(str(OUTPUT_DIR / f"desktop-{name}.png"))
            if name == "dashboard":
                assert_dashboard_containment(driver, "desktop")
                wait.until(
                    lambda current: "当前账号还没有做题记录"
                    not in current.find_element(By.TAG_NAME, "body").text
                )
                body = driver.find_element(By.TAG_NAME, "body").text
                assert "当前账号还没有做题记录" not in body
                assert "2024-05-18" not in body
                wait.until(lambda current: current.find_elements(By.CSS_SELECTOR, ".radar-sparse-list"))
            if name == "knowledge":
                assert_chart_fills_host(driver, "desktop")
            if name == "profile":
                wait.until(lambda current: current.find_elements(By.CSS_SELECTOR, ".radar-sparse-list"))
            if name == "messages":
                tabs = driver.find_elements(By.CSS_SELECTOR, ".message-center-tabs button")
                tabs[1].click()
                wait.until(lambda current: current.find_elements(By.CSS_SELECTOR, ".student-teacher-messages"))
                wait.until(lambda current: "active" in current.find_elements(By.CSS_SELECTOR, ".message-center-tabs button")[1].get_attribute("class"))
            assert_no_browser_errors(driver, "desktop", path)

        driver.set_window_size(1180, 900)
        driver.get(f"{BASE_URL}/")
        wait_for_vue(driver, wait)
        assert_healthy(driver, "大学数学学习中控台")
        assert_dashboard_containment(driver, "compact-desktop")
        assert_assistant_clear(driver, "compact-desktop", "/")
        driver.save_screenshot(str(OUTPUT_DIR / "compact-dashboard.png"))
        assert_no_browser_errors(driver, "compact-desktop", "/")

        driver.set_window_size(390, 844)
        driver.execute_cdp_cmd(
            "Emulation.setDeviceMetricsOverride",
            {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True},
        )
        for path, heading, name in pages:
            driver.get(f"{BASE_URL}{path}")
            wait_for_vue(driver, wait)
            assert_healthy(driver, heading)
            assert driver.find_element(By.CSS_SELECTOR, ".assistant-orb").is_displayed()
            assert_assistant_clear(driver, "mobile", path)
            if name == "dashboard":
                assignment_tab = driver.find_element(By.CSS_SELECTOR, ".student-side-nav a[href='/assignments']")
                assert assignment_tab.is_displayed(), "移动端 TabBar 必须包含我的作业"
            if name == "messages":
                tabs = driver.find_elements(By.CSS_SELECTOR, ".message-center-tabs button")
                tabs[1].click()
                wait.until(lambda current: current.find_elements(By.CSS_SELECTOR, ".student-teacher-messages"))
                wait.until(lambda current: "active" in current.find_elements(By.CSS_SELECTOR, ".message-center-tabs button")[1].get_attribute("class"))
            driver.save_screenshot(str(OUTPUT_DIR / f"mobile-{name}.png"))
            if name == "knowledge":
                assert_chart_fills_host(driver, "mobile")
            assert_no_browser_errors(driver, "mobile", path)
        network_failures = collect_network_failures(driver)
        assert not network_failures, network_failures
        print(f"STUDENT_BROWSER_OK screenshots={OUTPUT_DIR}")
    finally:
        if driver:
            driver.quit()
        with SessionLocal() as db:
            db.execute(text("DELETE FROM users WHERE id=:id"), {"id": user_id})
            db.commit()


if __name__ == "__main__":
    main()
