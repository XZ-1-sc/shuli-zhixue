"""Browser smoke test for the teacher portal running at localhost:8080."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import InvalidArgumentException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support import expected_conditions as expected
from selenium.webdriver.support.ui import Select, WebDriverWait
from sqlalchemy import text


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.database.session import SessionLocal  # noqa: E402


BASE_URL = "http://localhost:8080"
TEACHER_USERNAME = os.environ.get("E2E_TEACHER_USERNAME", "")
TEACHER_PASSWORD = os.environ.get("E2E_TEACHER_PASSWORD", "")
STUDENT_USERNAME = os.environ.get("E2E_STUDENT_USERNAME", "")
OUTPUT_DIR = ROOT / "tmp" / "teacher-browser"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def wait_for_vue(driver: webdriver.Edge, wait: WebDriverWait) -> None:
    wait.until(lambda current: current.execute_script("return document.readyState") == "complete")
    wait.until(lambda current: len(current.find_elements(By.CSS_SELECTOR, "#app > *")) > 0)
    time.sleep(0.35)


def click_nav(driver: webdriver.Edge, wait: WebDriverWait, label: str, path: str) -> None:
    link = wait.until(
        expected.element_to_be_clickable(
            (
                By.XPATH,
                "//aside[contains(@class,'teacher-sidebar')]//a[.//strong[normalize-space()="
                f"'{label}']]",
            )
        )
    )
    driver.execute_script("arguments[0].click()", link)
    wait.until(lambda current: current.current_url.split("?", 1)[0].endswith(path))
    wait_for_vue(driver, wait)


def screenshot(driver: webdriver.Edge, name: str) -> None:
    driver.save_screenshot(str(OUTPUT_DIR / f"{name}.png"))


def assert_page_healthy(driver: webdriver.Edge, expected_heading: str) -> None:
    body_text = driver.find_element(By.TAG_NAME, "body").text
    assert expected_heading in body_text, f"Page heading missing: {expected_heading}"
    forbidden = ["加载失败", "暂时无法加载", "Failed to fetch", "Internal Server Error"]
    assert not any(item in body_text for item in forbidden), body_text[:1000]
    dimensions = driver.execute_script(
        "return {viewport: innerWidth, width: document.documentElement.scrollWidth};"
    )
    if dimensions["width"] > dimensions["viewport"] + 4:
        offenders = driver.execute_script(
            """
            return [...document.querySelectorAll('body *')]
              .map((element) => {
                const rect = element.getBoundingClientRect();
                return {
                  tag: element.tagName,
                  className: typeof element.className === 'string' ? element.className : '',
                  left: Math.round(rect.left),
                  right: Math.round(rect.right),
                  width: Math.round(rect.width),
                  scrollWidth: element.scrollWidth
                };
              })
              .filter((item) => item.right > innerWidth + 4 || item.left < -4)
              .sort((a, b) => b.right - a.right)
              .slice(0, 20);
            """
        )
        raise AssertionError({"dimensions": dimensions, "offenders": offenders})


def collect_network_failures(driver: webdriver.Edge) -> list[dict[str, object]]:
    failures: list[dict[str, object]] = []
    try:
        entries = driver.get_log("performance")
    except InvalidArgumentException:
        # Some Edge builds expose browser logs but not Chromium performance logs.
        return failures
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


def cleanup_class(class_name: str) -> None:
    with SessionLocal() as db:
        class_ids = [
            int(row[0])
            for row in db.execute(
                text("SELECT id FROM classes WHERE name=:name"), {"name": class_name}
            ).all()
        ]
        for class_id in class_ids:
            db.execute(text("DELETE FROM class_members WHERE class_id=:id"), {"id": class_id})
            db.execute(
                text("DELETE FROM audit_logs WHERE entity_type='class' AND entity_id=:id"),
                {"id": class_id},
            )
            db.execute(text("DELETE FROM classes WHERE id=:id"), {"id": class_id})
        db.execute(
            text("DELETE FROM user_notifications WHERE content LIKE :pattern"),
            {"pattern": f"%{class_name}%"},
        )
        db.commit()


def main() -> None:
    if not all((TEACHER_USERNAME, TEACHER_PASSWORD, STUDENT_USERNAME)):
        raise RuntimeError(
            "请设置 E2E_TEACHER_USERNAME、E2E_TEACHER_PASSWORD、E2E_STUDENT_USERNAME 后运行浏览器回归。"
        )
    marker = str(int(time.time()))
    class_name = f"浏览器回归班-{marker}"
    options = Options()
    options.binary_location = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1600,1000")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-first-run")
    options.add_argument("--disable-features=msEdgeSidebarV2")
    options.set_capability("goog:loggingPrefs", {"browser": "ALL", "performance": "ALL"})

    driver: webdriver.Edge | None = None
    try:
        driver = webdriver.Edge(options=options)
        driver.set_page_load_timeout(35)
        wait = WebDriverWait(driver, 25)

        driver.get(f"{BASE_URL}/auth?role=teacher&mode=login")
        wait_for_vue(driver, wait)
        driver.find_element(By.CSS_SELECTOR, "input[autocomplete='username']").send_keys(TEACHER_USERNAME)
        driver.find_element(By.CSS_SELECTOR, "input[autocomplete='current-password']").send_keys(TEACHER_PASSWORD)
        driver.find_element(By.CSS_SELECTOR, ".identity-submit").click()
        wait.until(lambda current: current.current_url.rstrip("/").endswith("/teacher"))
        wait.until(expected.presence_of_element_located((By.CSS_SELECTOR, ".teacher-sidebar")))
        assert_page_healthy(driver, "教师工作台")
        screenshot(driver, "01-dashboard")

        expected_nav = ["工作台", "班级管理", "学生学情", "题库管理", "作业管理", "批改中心"]
        actual_nav = [
            item.text.strip()
            for item in driver.find_elements(By.CSS_SELECTOR, ".teacher-sidebar nav a strong")
        ]
        assert actual_nav == expected_nav, actual_nav

        click_nav(driver, wait, "班级管理", "/teacher/classes")
        assert_page_healthy(driver, "班级管理")
        screenshot(driver, "02-classes")

        create_button = wait.until(
            expected.element_to_be_clickable(
                (By.XPATH, "//button[contains(normalize-space(),'创建班级')]")
            )
        )
        create_button.click()
        modal = wait.until(expected.visibility_of_element_located((By.CSS_SELECTOR, ".teacher-modal")))
        modal.find_element(By.CSS_SELECTOR, "input").send_keys(class_name)
        selects = modal.find_elements(By.CSS_SELECTOR, "select")
        Select(selects[0]).select_by_visible_text(
            next(option.text for option in Select(selects[0]).options if option.text.startswith("大一"))
        )
        wait.until(lambda _: len(Select(selects[1]).options) > 0)
        Select(selects[1]).select_by_index(0)
        modal.find_element(
            By.XPATH, ".//button[@type='submit' and contains(normalize-space(),'创建班级')]"
        ).click()
        wait.until(lambda current: class_name in current.find_element(By.TAG_NAME, "body").text)

        student_input = wait.until(
            expected.element_to_be_clickable((By.CSS_SELECTOR, "input[placeholder*='树虫']"))
        )
        student_input.send_keys(STUDENT_USERNAME)
        driver.find_element(
            By.XPATH, "//form[contains(@class,'teacher-add-student-form')]//button[@type='submit']"
        ).click()
        wait.until(lambda current: "已加入" in current.find_element(By.TAG_NAME, "body").text)
        assert STUDENT_USERNAME in driver.find_element(By.TAG_NAME, "body").text

        export_button = driver.find_element(
            By.XPATH, "//button[normalize-space()='导出名单']"
        )
        assert export_button.is_enabled()

        regenerate = driver.find_element(
            By.XPATH, "//button[contains(normalize-space(),'重新生成')]"
        )
        regenerate.click()
        confirm_dialog = wait.until(
            expected.visibility_of_element_located((By.CSS_SELECTOR, ".confirm-dialog"))
        )
        confirm_dialog.find_element(By.CSS_SELECTOR, ".confirm-submit").click()
        wait.until(lambda current: "新的班级邀请码已生成" in current.find_element(By.TAG_NAME, "body").text)
        screenshot(driver, "03-class-created")

        click_nav(driver, wait, "学生学情", "/teacher/students")
        assert_page_healthy(driver, "学生学情")
        screenshot(driver, "04-students")

        click_nav(driver, wait, "题库管理", "/teacher/questions")
        assert_page_healthy(driver, "题库管理")
        wait.until(
            expected.element_to_be_clickable(
                (By.XPATH, "//button[contains(normalize-space(),'文件导入')]")
            )
        ).click()
        import_dialog = wait.until(
            expected.visibility_of_element_located((By.CSS_SELECTOR, ".teacher-import-dialog"))
        )
        assert "从文件导入题目" in import_dialog.text
        assert ".pdf" in import_dialog.find_element(By.CSS_SELECTOR, "input[type='file']").get_attribute("accept")
        screenshot(driver, "05-question-import")
        import_dialog.find_element(By.CSS_SELECTOR, "button[aria-label='关闭']").click()
        wait.until(expected.invisibility_of_element_located((By.CSS_SELECTOR, ".teacher-import-dialog")))
        wait.until(
            expected.element_to_be_clickable(
                (By.CSS_SELECTOR, "a[href='/teacher/questions/new']")
            )
        ).click()
        wait.until(lambda current: current.current_url.endswith("/teacher/questions/new"))
        wait_for_vue(driver, wait)
        assert_page_healthy(driver, "新建题目")
        assert driver.find_element(By.CSS_SELECTOR, "input[type='file']").get_attribute("accept")
        screenshot(driver, "05-question-editor")

        driver.get(f"{BASE_URL}/teacher/assignments")
        wait_for_vue(driver, wait)
        assert_page_healthy(driver, "作业管理")
        wait.until(
            expected.element_to_be_clickable(
                (By.CSS_SELECTOR, "a[href='/teacher/assignments/new']")
            )
        ).click()
        wait.until(lambda current: current.current_url.endswith("/teacher/assignments/new"))
        wait_for_vue(driver, wait)
        assert_page_healthy(driver, "布置作业")
        random_button = wait.until(
            expected.element_to_be_clickable(
                (By.XPATH, "//button[contains(normalize-space(),'随机选题')]")
            )
        )
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", random_button)
        time.sleep(0.25)
        random_button.click()
        wait.until(
            lambda current: "已随机加入" in current.find_element(By.TAG_NAME, "body").text
            or "暂无可用中文题" in current.find_element(By.TAG_NAME, "body").text
        )
        assert "已随机加入" in driver.find_element(By.TAG_NAME, "body").text
        upload_paper = wait.until(
            expected.element_to_be_clickable(
                (By.XPATH, "//button[contains(normalize-space(),'上传试卷')]")
            )
        )
        upload_paper.click()
        paper_dialog = wait.until(
            expected.visibility_of_element_located((By.CSS_SELECTOR, ".teacher-import-dialog"))
        )
        assert "上传试卷并加入当前作业" in paper_dialog.text
        screenshot(driver, "06b-paper-import")
        paper_dialog.find_element(By.CSS_SELECTOR, "button[aria-label='关闭']").click()
        screenshot(driver, "06-assignment-editor")

        click_nav(driver, wait, "批改中心", "/teacher/review")
        assert_page_healthy(driver, "批改中心")
        screenshot(driver, "07-review")

        driver.set_window_size(390, 844)
        driver.execute_cdp_cmd(
            "Emulation.setDeviceMetricsOverride",
            {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True},
        )
        mobile_pages = [
            ("/teacher", "教师工作台", "08-mobile-dashboard"),
            ("/teacher/classes", "班级管理", "09-mobile-classes"),
            ("/teacher/questions", "题库管理", "10-mobile-questions"),
            ("/teacher/questions/new", "新建题目", "10b-mobile-question-editor"),
            ("/teacher/assignments", "作业管理", "11-mobile-assignments"),
            ("/teacher/assignments/new", "布置作业", "11b-mobile-assignment-editor"),
            ("/teacher/review", "批改中心", "12-mobile-review"),
        ]
        for path, heading, image_name in mobile_pages:
            driver.get(f"{BASE_URL}{path}")
            wait_for_vue(driver, wait)
            assert_page_healthy(driver, heading)
            screenshot(driver, image_name)

        browser_errors = [
            entry for entry in driver.get_log("browser") if entry.get("level") == "SEVERE"
        ]
        network_failures = collect_network_failures(driver)
        assert not browser_errors, browser_errors
        assert not network_failures, network_failures
        print(f"TEACHER_BROWSER_OK screenshots={OUTPUT_DIR}")
    except TimeoutException as exc:
        if driver:
            screenshot(driver, "failure-timeout")
        raise AssertionError("Browser flow timed out; failure screenshot was saved.") from exc
    finally:
        if driver:
            driver.quit()
        cleanup_class(class_name)


if __name__ == "__main__":
    main()
