"""Desktop and mobile browser acceptance test for class deletion."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support import expected_conditions as expected
from selenium.webdriver.support.ui import WebDriverWait
from sqlalchemy import text


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.database.session import SessionLocal  # noqa: E402
from app.utils.password import hash_password  # noqa: E402


BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8080").rstrip("/")
PASSWORD = "Class-Delete-Browser-QA-2026!"
OUTPUT_DIR = ROOT / "tmp" / "class-delete-browser"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def wait_for_vue(driver: webdriver.Edge, wait: WebDriverWait) -> None:
    wait.until(lambda current: current.execute_script("return document.readyState") == "complete")
    wait.until(lambda current: current.find_elements(By.CSS_SELECTOR, "#app > *"))
    time.sleep(0.3)


def take_screenshot(driver: webdriver.Edge, name: str) -> None:
    driver.save_screenshot(str(OUTPUT_DIR / f"{name}.png"))


def assert_dialog_layer(driver: webdriver.Edge) -> None:
    result = driver.execute_script(
        """
        const backdrop = document.querySelector('.teacher-delete-backdrop');
        const modal = document.querySelector('.teacher-delete-modal');
        const rect = modal.getBoundingClientRect();
        const visible = [...document.querySelectorAll('body *')]
          .filter((node) => node !== backdrop && node !== modal && !node.closest('.teacher-delete-backdrop'))
          .map((node) => ({node, rect: node.getBoundingClientRect(), style: getComputedStyle(node)}))
          .filter((item) => item.style.position === 'fixed' && item.rect.width > 0 && item.rect.height > 0);
        return {
          backdropZ: Number(getComputedStyle(backdrop).zIndex || 0),
          competingFixedZ: Math.max(0, ...visible.map((item) => Number(item.style.zIndex || 0))),
          viewportWidth: innerWidth,
          viewportHeight: innerHeight,
          left: rect.left,
          right: rect.right,
          top: rect.top,
          bottom: rect.bottom,
          modalClientWidth: modal.clientWidth,
          modalScrollWidth: modal.scrollWidth,
          documentWidth: document.documentElement.scrollWidth
        };
        """
    )
    assert result["backdropZ"] > result["competingFixedZ"], result
    assert result["left"] >= -1 and result["right"] <= result["viewportWidth"] + 1, result
    assert result["top"] >= -1 and result["bottom"] <= result["viewportHeight"] + 1, result
    assert result["modalScrollWidth"] <= result["modalClientWidth"] + 1, result
    assert result["documentWidth"] <= result["viewportWidth"] + 4, result


def main() -> None:
    marker = str(int(time.time() * 1000))
    username = f"qa_class_delete_browser_{marker}"
    student_username = f"qa_class_delete_browser_student_{marker}"
    data_class_name = f"桌面删除验收班-{marker}"
    empty_class_name = f"手机删除验收班-{marker}"
    teacher_id = student_id = data_class_id = empty_class_id = None
    driver: webdriver.Edge | None = None

    try:
        with SessionLocal() as db:
            teacher = db.execute(
                text(
                    "INSERT INTO users (username,password_hash,nickname,role,current_stage,status) "
                    "VALUES (:username,:password_hash,:username,'teacher','大一',1)"
                ),
                {"username": username, "password_hash": hash_password(PASSWORD)},
            )
            teacher_id = int(teacher.lastrowid)
            db.execute(
                text("INSERT INTO teacher_profiles (user_id,display_name) VALUES (:id,:name)"),
                {"id": teacher_id, "name": username},
            )
            student = db.execute(
                text(
                    "INSERT INTO users (username,password_hash,nickname,role,current_stage,status) "
                    "VALUES (:username,:password_hash,:username,'student','大一',1)"
                ),
                {"username": student_username, "password_hash": hash_password(PASSWORD)},
            )
            student_id = int(student.lastrowid)
            data_class = db.execute(
                text(
                    "INSERT INTO classes (teacher_id,name,stage,course,invite_code,status) "
                    "VALUES (:teacher_id,:name,'大一','高等数学',:code,'active')"
                ),
                {"teacher_id": teacher_id, "name": data_class_name, "code": f"D1{marker[-6:]}"},
            )
            data_class_id = int(data_class.lastrowid)
            db.execute(
                text("INSERT INTO class_members (class_id,student_id,status) VALUES (:class_id,:student_id,'active')"),
                {"class_id": data_class_id, "student_id": student_id},
            )
            db.execute(
                text(
                    "INSERT INTO assignments (teacher_id,class_id,title,status,total_score) "
                    "VALUES (:teacher_id,:class_id,:title,'closed',10)"
                ),
                {"teacher_id": teacher_id, "class_id": data_class_id, "title": f"浏览器删除验收作业-{marker}"},
            )
            empty_class = db.execute(
                text(
                    "INSERT INTO classes (teacher_id,name,stage,course,invite_code,status) "
                    "VALUES (:teacher_id,:name,'大一','高等数学',:code,'active')"
                ),
                {"teacher_id": teacher_id, "name": empty_class_name, "code": f"D2{marker[-6:]}"},
            )
            empty_class_id = int(empty_class.lastrowid)
            db.commit()

        options = Options()
        options.binary_location = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1600,1000")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-first-run")
        options.add_argument("--disable-features=msEdgeSidebarV2")
        options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
        driver = webdriver.Edge(options=options)
        driver.set_page_load_timeout(35)
        wait = WebDriverWait(driver, 25)

        driver.get(f"{BASE_URL}/auth?role=teacher&mode=login")
        wait_for_vue(driver, wait)
        driver.find_element(By.CSS_SELECTOR, "input[autocomplete='username']").send_keys(username)
        driver.find_element(By.CSS_SELECTOR, "input[autocomplete='current-password']").send_keys(PASSWORD)
        driver.find_element(By.CSS_SELECTOR, ".identity-submit").click()
        wait.until(lambda current: current.current_url.rstrip("/").endswith("/teacher"))

        driver.get(f"{BASE_URL}/teacher/classes?class_id={data_class_id}")
        wait_for_vue(driver, wait)
        wait.until(lambda current: data_class_name in current.find_element(By.TAG_NAME, "body").text)
        wait.until(expected.element_to_be_clickable((By.CSS_SELECTOR, "button.is-delete"))).click()
        dialog = wait.until(expected.visibility_of_element_located((By.CSS_SELECTOR, ".teacher-delete-modal")))
        wait.until(lambda current: not current.find_elements(By.CSS_SELECTOR, ".teacher-delete-loading"))
        assert_dialog_layer(driver)
        assert data_class_name in dialog.text
        assert all(label in dialog.text for label in ("1\n名学生", "1\n份作业", "0\n条关联作答")), dialog.text
        delete_button = dialog.find_element(By.CSS_SELECTOR, ".teacher-delete-submit")
        name_input = dialog.find_element(By.CSS_SELECTOR, ".teacher-delete-name-field input")
        assert not delete_button.is_enabled()
        name_input.send_keys("错误班级名")
        assert not delete_button.is_enabled()
        name_input.clear()
        name_input.send_keys(data_class_name)
        wait.until(lambda _: delete_button.is_enabled())
        take_screenshot(driver, "desktop-data-confirm")
        delete_button.click()
        wait.until(expected.invisibility_of_element_located((By.CSS_SELECTOR, ".teacher-delete-modal")))
        wait.until(lambda current: data_class_name not in current.find_element(By.CSS_SELECTOR, ".teacher-class-list").text)

        driver.set_window_size(430, 900)
        driver.execute_cdp_cmd(
            "Emulation.setDeviceMetricsOverride",
            {"width": 430, "height": 900, "deviceScaleFactor": 1, "mobile": True},
        )
        driver.get(f"{BASE_URL}/teacher/classes?class_id={empty_class_id}")
        wait_for_vue(driver, wait)
        wait.until(lambda current: empty_class_name in current.find_element(By.TAG_NAME, "body").text)
        delete_entry = wait.until(expected.presence_of_element_located((By.CSS_SELECTOR, "button.is-delete")))
        driver.execute_script("arguments[0].click();", delete_entry)
        mobile_dialog = wait.until(expected.visibility_of_element_located((By.CSS_SELECTOR, ".teacher-delete-modal")))
        wait.until(lambda current: not current.find_elements(By.CSS_SELECTOR, ".teacher-delete-loading"))
        assert_dialog_layer(driver)
        assert empty_class_name in mobile_dialog.text
        assert "该班级没有成员、作业或关联作答" in mobile_dialog.text
        assert not mobile_dialog.find_elements(By.CSS_SELECTOR, ".teacher-delete-name-field")
        mobile_delete_button = mobile_dialog.find_element(By.CSS_SELECTOR, ".teacher-delete-submit")
        assert mobile_delete_button.is_enabled()
        take_screenshot(driver, "mobile-empty-confirm")
        mobile_delete_button.click()
        wait.until(expected.invisibility_of_element_located((By.CSS_SELECTOR, ".teacher-delete-modal")))

        browser_errors = [entry for entry in driver.get_log("browser") if entry.get("level") == "SEVERE"]
        assert not browser_errors, browser_errors
        print(f"CLASS_DELETE_BROWSER_OK screenshots={OUTPUT_DIR}")
    except TimeoutException as exc:
        if driver:
            take_screenshot(driver, "failure-timeout")
        raise AssertionError("班级删除页面验收超时，已保存失败截图。") from exc
    finally:
        if driver:
            driver.quit()
        if teacher_id:
            with SessionLocal() as db:
                db.execute(text("DELETE FROM auth_sessions WHERE user_id IN (:teacher,:student)"), {"teacher": teacher_id, "student": student_id})
                db.execute(text("DELETE FROM teacher_profiles WHERE user_id=:teacher"), {"teacher": teacher_id})
                db.execute(text("DELETE FROM users WHERE id IN (:teacher,:student)"), {"teacher": teacher_id, "student": student_id})
                db.commit()


if __name__ == "__main__":
    main()
