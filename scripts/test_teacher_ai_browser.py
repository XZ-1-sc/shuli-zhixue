"""AI dialog regression in real Edge with an entirely mocked API (no model/DB writes).

Build frontend first, then python scripts/test_teacher_ai_browser.py.
Optional --root points to another checkout; --url tests the deployed gateway.
Selenium and Microsoft Edge are required (pip install selenium).
"""
import argparse
import functools
import json
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
from selenium.webdriver.support.ui import Select, WebDriverWait

ROOT = Path(__file__).resolve().parents[1]


class SpaHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        if "." not in self.path.rsplit("/", 1)[-1]:
            self.path = "/index.html"
        super().do_GET()

    def log_message(self, *_args):
        pass


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--url")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    output = args.root / "tmp" / "teacher-ai-browser"
    output.mkdir(parents=True, exist_ok=True)
    server = None
    if not args.url:
        server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(SpaHandler, directory=str(args.root / "frontend/dist")))
        threading.Thread(target=server.serve_forever, daemon=True).start()
    base = args.url or f"http://localhost:{server.server_port}"
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-first-run")
    options.add_argument("--window-size=1440,900")
    options.set_capability("ms:loggingPrefs", {"browser": "ALL"})
    cache = Path.home() / ".cache/selenium/msedgedriver/win64"
    drivers = sorted(cache.glob("*/msedgedriver.exe"), key=lambda path: tuple(map(int, path.parent.name.split("."))))
    driver = webdriver.Edge(service=Service(str(drivers[-1])) if drivers else Service(), options=options)
    wait = WebDriverWait(driver, 15)
    report = {"layout_cases": [], "flows": []}

    def js(code, *values):
        return driver.execute_script(code, *values)

    def click(selector):
        if selector.startswith((".page-header-actions", ".class-heading-side")):
            close_assistant()
        wait.until(lambda _: driver.find_element(By.CSS_SELECTOR, selector).is_displayed())
        driver.find_element(By.CSS_SELECTOR, selector).click()

    def viewport(width, height, scale=1):
        driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
            "width": width, "height": height, "deviceScaleFactor": scale, "mobile": False
        })

    def layout():
        result = js("""
          const modal = document.querySelector('.teacher-ai-question-modal');
          const button = modal.querySelector('[type=submit]');
          const body = modal.querySelector('.ai-question-body');
          const r = button.getBoundingClientRect(), m = modal.getBoundingClientRect();
          const header = modal.querySelector('header').getBoundingClientRect();
          const footer = modal.querySelector('.ai-question-actions').getBoundingClientRect();
          const b = body.getBoundingClientRect();
          const hit = document.elementFromPoint(r.x+r.width/2, r.y+r.height/2);
          return {visible:r.top>=0 && r.bottom<=innerHeight && r.left>=0 && r.right<=innerWidth,
            hit:hit===button || button.contains(hit), bounded:m.top>=0 && m.bottom<=innerHeight+1,
            separate:header.bottom<=b.top+1 && b.bottom<=footer.top+1,
            overflow:modal.scrollWidth<=modal.clientWidth+1,
            bodyHeight:b.height, top:r.top, bottom:r.bottom};
        """)
        assert all(result[key] for key in ["visible", "hit", "bounded", "separate", "overflow"]), result
        assert result["bodyHeight"] > 80, result
        return result

    def ready():
        wait.until(lambda _: js("return !!document.querySelector('.ai-question-generate') && !document.querySelector('.ai-question-generate').disabled"))

    def request_count():
        return js("return window.__aiTest.requests.length")

    def close_assistant():
        wait.until(lambda _: js("return !!document.querySelector('.assistant-drawer')"))
        # Cancel the existing delayed auto-open on versions which support it,
        # then use the close handler shared by all supported versions.
        js("window.dispatchEvent(new Event('xiaoluo:close')); document.querySelector('.assistant-drawer.is-open button[aria-label=关闭小逻]')?.click()")
        wait.until(lambda _: not js("return document.querySelector('.assistant-drawer').classList.contains('is-open')"))

    try:
        fixture = (ROOT / "scripts/fixtures/teacher_ai_browser.js").read_text(encoding="utf-8")
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": fixture})
        driver.get(base + "/teacher/questions")
        close_assistant()
        click(".page-header-actions button:first-child")
        ready()
        types = ["choice", "blank", "calculation", "proof", "comprehensive"]
        # Reduced CSS viewport with higher DPR reproduces browser zoom/reflow.
        sizes = [(1440, 900, 1), (1366, 768, 1), (1280, 600, 1), (375, 667, 1), (320, 568, 1), (911, 512, 1.5), (683, 384, 2)]
        for width, height, scale in sizes:
            viewport(width, height, scale)
            for question_type in types:
                Select(driver.find_element(By.CSS_SELECTOR, "[name=question_type]")).select_by_value(question_type)
                info = layout()
                report["layout_cases"].append({"width": width, "height": height, "zoom": scale, "type": question_type, **info})
            driver.save_screenshot(str(output / f"dialog-{width}x{height}.png"))
        # Empty required field must not reach the server.
        click(".ai-question-generate")
        assert request_count() == 0
        assert not js("return document.querySelector('[name=knowledge_tag]').validity.valid")
        report["flows"].append("required validation")
        field = driver.find_element(By.CSS_SELECTOR, "[name=knowledge_tag]")
        field.send_keys("函数与极限")
        count_field = driver.find_element(By.CSS_SELECTOR, "[name=count]")
        count_field.send_keys(Keys.CONTROL, "a")
        count_field.send_keys("5")
        js("window.__aiTest.hold = true")
        click(".ai-question-generate")
        wait.until(lambda _: request_count() == 1)
        assert "生成与校验中" in driver.find_element(By.CSS_SELECTOR, ".ai-question-generate").text
        assert not driver.find_element(By.CSS_SELECTOR, ".ai-question-generate").is_enabled()
        # Exercise both disabled clicks and the method-level re-entry guard.
        js("document.querySelector('.ai-question-generate').click(); document.querySelector('.teacher-ai-question-modal').dispatchEvent(new Event('submit', {cancelable:true,bubbles:true}))")
        assert request_count() == 1
        js("window.__aiTest.hold=false;window.__aiTest.release()")
        ready()
        wait.until(lambda _: len(driver.find_elements(By.CSS_SELECTOR, ".ai-question-result")) == 5)
        assert driver.find_element(By.CSS_SELECTOR, ".ai-question-generate").text == "再生成一批"
        for width, height, scale in sizes:
            viewport(width, height, scale)
            for question_type in types:
                Select(driver.find_element(By.CSS_SELECTOR, "[name=question_type]")).select_by_value(question_type)
                before = layout()
                js("document.querySelector('.ai-question-body').scrollTop=100000")
                after = layout()
                assert abs(before["top"] - after["top"]) < 1
            driver.save_screenshot(str(output / f"results-{width}x{height}.png"))
        report["flows"].extend(["busy/duplicate guard", "five results", "fixed actions while scrolling", "all types after results"])
        # Test each type's actual request payload and regeneration.
        viewport(1366, 768)
        for question_type in types:
            Select(driver.find_element(By.CSS_SELECTOR, "[name=question_type]")).select_by_value(question_type)
            previous = request_count()
            click(".ai-question-generate")
            wait.until(lambda _: request_count() == previous + 1)
            ready()
            assert js("return window.__aiTest.requests.at(-1).question_type") == question_type
            layout()
        report["flows"].append("five types/regenerate")
        js("window.__aiTest.mode='error'")
        click(".ai-question-generate")
        ready()
        wait.until(lambda _: js("return document.querySelector('[role=alert]')?.textContent.includes('模型服务不可用')"))
        layout()
        js("window.__aiTest.mode='zero'")
        click(".ai-question-generate")
        ready()
        wait.until(lambda _: "本次未生成题目" in driver.find_element(By.CSS_SELECTOR, ".ai-question-results").text)
        layout()
        report["flows"].extend(["API error recovery", "zero success"])
        # Keyboard trapping, Escape and scroll restoration.
        js("document.querySelector('.ai-question-generate').focus()")
        driver.switch_to.active_element.send_keys(Keys.TAB)
        assert js("return document.activeElement.classList.contains('ai-question-dismiss')")
        driver.switch_to.active_element.send_keys(Keys.ESCAPE)
        wait.until(lambda _: not driver.find_elements(By.CSS_SELECTOR, ".teacher-ai-question-modal"))
        assert js("return document.body.style.overflow") != "hidden"
        assert js("return document.activeElement.textContent.includes('AI 出题')")
        # Filters still issue correctly scoped list requests.
        Select(driver.find_element(By.CSS_SELECTOR, ".teacher-question-filters select")).select_by_value("public")
        wait.until(lambda _: js("return window.__aiTest.queries.at(-1).scope==='public'"))
        click(".page-header-actions button:first-child")
        ready()
        js("window.__aiTest.mode='success'")
        click(".ai-question-generate")
        ready()
        click(".ai-question-results > a")
        wait.until(lambda _: "/edit" in driver.current_url)
        assert not driver.find_elements(By.CSS_SELECTOR, ".teacher-ai-question-modal")
        wait.until(lambda _: js("return [...document.querySelectorAll('textarea')].some(el=>el.value.includes('浏览器测试题'))"))
        report["flows"].extend(["keyboard/focus/scroll restoration", "question filters", "review editor navigation"])
        # Unrelated import and class dialogs should still open and close.
        driver.get(base + "/teacher/questions")
        close_assistant()
        click(".page-header-actions button:nth-child(2)")
        wait.until(lambda _: driver.find_element(By.CSS_SELECTOR, ".teacher-import-dialog").is_displayed())
        click(".teacher-import-header button")
        viewport(1440, 900)
        driver.get(base + "/teacher/classes")
        close_assistant()
        click(".page-header-actions button")
        wait.until(lambda _: driver.find_element(By.CSS_SELECTOR, ".teacher-modal").is_displayed())
        click(".teacher-modal header button")
        wait.until(lambda _: not driver.find_elements(By.CSS_SELECTOR, ".teacher-modal"))
        click(".class-heading-side .is-delete")
        wait.until(lambda _: driver.find_element(By.CSS_SELECTOR, ".teacher-delete-modal").is_displayed())
        click(".teacher-delete-modal header button")
        wait.until(lambda _: not driver.find_elements(By.CSS_SELECTOR, ".teacher-delete-modal"))
        report["flows"].extend(["file import modal", "create class modal", "delete class modal (cancel only)"])
        severe = [entry for entry in driver.get_log("browser") if entry["level"] == "SEVERE"]
        assert not severe, severe
        report["browser"] = driver.capabilities["browserVersion"]
        report["status"] = "PASS"
        (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print("TEACHER_AI_BROWSER_OK " + json.dumps({"layout_cases": len(report["layout_cases"]), "flows": report["flows"]}, ensure_ascii=False))
    except Exception:
        driver.save_screenshot(str(output / "failed.png"))
        print(json.dumps(js("return {url:location.href,text:document.body.innerText.slice(-2000), requests:window.__aiTest?.requests}"), ensure_ascii=False))
        raise
    finally:
        driver.quit()
        if server:
            server.shutdown()


if __name__ == "__main__":
    main()
