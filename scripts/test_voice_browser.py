"""Voice UI regression in real headless Edge using simulated speech and chat events.

No microphone recording, model calls, database writes or real account changes.
The --url option checks the deployed gateway; otherwise serve frontend/dist locally.
"""
from __future__ import annotations

import argparse
import functools
import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
from selenium.webdriver.support.ui import WebDriverWait

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "tmp" / "voice-browser"


class SpaHandler(SimpleHTTPRequestHandler):
    def handle(self):
        try:
            super().handle()
        except ConnectionResetError:
            pass

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
    parser = argparse.ArgumentParser()
    parser.add_argument("--url")
    args = parser.parse_args()
    server = None
    if not args.url:
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            functools.partial(SpaHandler, directory=str(ROOT / "frontend" / "dist")),
        )
        threading.Thread(target=server.serve_forever, daemon=True).start()
    base = args.url or f"http://localhost:{server.server_port}"
    OUTPUT.mkdir(parents=True, exist_ok=True)
    options = Options()
    options.binary_location = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1440,1000")
    options.add_argument("--no-first-run")
    options.add_argument("--disable-features=msEdgeSidebarV2")
    options.set_capability("ms:loggingPrefs", {"browser": "ALL"})
    cached = Path.home() / ".cache" / "selenium" / "msedgedriver" / "win64"
    drivers = sorted(cached.glob("*/msedgedriver.exe"), key=lambda path: tuple(map(int, path.parent.name.split("."))))
    driver = webdriver.Edge(service=Service(str(drivers[-1])) if drivers else Service(), options=options)
    wait = WebDriverWait(driver, 15)

    def js(code, *values):
        return driver.execute_script(code, *values)

    def state(value):
        wait.until(lambda _: js("return !!document.querySelector('.voice-status.voice-' + arguments[0])", value))

    def click(selector):
        wait.until(lambda _: driver.find_element(By.CSS_SELECTOR, selector).is_displayed())
        driver.find_element(By.CSS_SELECTOR, selector).click()

    def hear(text, final=True):
        js("window.__voiceTest.hear(arguments[0], arguments[1])", text, final)

    def finish():
        js("let chunks = 0; while (speechSynthesis.current && chunks++ < 200) window.__voiceTest.finish()")
        state("listening")

    def count():
        return js("return window.__voiceTest.requests.length")

    def healthy_layout():
        issues = js("""
          const drawer = document.querySelector('.assistant-drawer');
          const box = drawer.getBoundingClientRect();
          const children = [...drawer.children].filter(el => el.getBoundingClientRect().height > 0);
          const errors = [];
          for (let i = 1; i < children.length; i++) {
            if (children[i].getBoundingClientRect().top < children[i-1].getBoundingClientRect().bottom - 2)
              errors.push('overlap:' + children[i].className);
          }
          if (box.left < -1 || box.right > innerWidth + 1 || box.bottom > innerHeight + 1) errors.push('drawer bounds');
          for (const selector of ['.chat-form', '.message-list', '.assistant-head', '.voice-panel']) {
            const el = drawer.querySelector(selector);
            const r = el.getBoundingClientRect();
            if (r.bottom > box.bottom + 1 || r.left < box.left - 1 || r.right > box.right + 1)
              errors.push('child bounds:' + selector);
          }
          if (drawer.querySelector('.message-list').clientHeight < 70) errors.push('conversation too small');
          return errors;
        """)
        assert not issues, issues

    report = {}
    try:
        # Probe installed browser APIs/voices without opening the microphone.
        driver.get(base + "/auth")
        report["browser"] = driver.capabilities["browserVersion"]
        report["native"] = driver.execute_async_script("""
          const done = arguments[arguments.length - 1];
          speechSynthesis.getVoices();
          setTimeout(() => done({
            secure: isSecureContext,
            recognition: !!(window.SpeechRecognition || window.webkitSpeechRecognition),
            chinese_voices: speechSynthesis.getVoices().filter(v => /^(zh|cmn)/i.test(v.lang))
              .map(v => ({name: v.name, local: v.localService}))
          }), 1000);
        """)
        source = (ROOT / "frontend/tests/voice-browser-fixture.js").read_text(encoding="utf-8")
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": source})
        driver.get(base + "/teacher/messages")
        wait.until(lambda _: js("return !!document.querySelector('.assistant-drawer.is-open')"))
        state("off")
        click(".voice-toggle")
        state("wake")
        click(".assistant-head button[aria-label='关闭小逻']")
        hear("你好小逻")
        state("speaking")
        wait.until(lambda _: js("return document.querySelector('.assistant-drawer').classList.contains('is-open')"))
        assert js("return window.__voiceTest.spoken.at(-1).text") == "我在，请讲。"
        finish()

        for question in ["极限怎么求", "再讲一个例子"]:
            previous = count()
            hear(question)
            state("speaking")
            assert count() == previous + 1
            assert js("return window.__voiceTest.requests.at(-1).message") == question
            finish()

        hear("请介绍导数")
        state("speaking")
        before = count()
        hear("先观察函数的变化。")
        assert count() == before
        state("speaking")
        hear("换个解法", False)
        state("listening")
        hear("换个解法说明")
        state("speaking")
        assert count() == before + 1
        click(".voice-status button")
        state("listening")

        # Preserve manually prepared draft/context when voice submits through send().
        js("""window.dispatchEvent(new CustomEvent('xiaoluo:open', {detail: {
          prompt: '暂存的文字草稿', autoSend:false, context:{type:'solution_step', question_id:42, step_no:2}
        }}))""")
        wait.until(lambda _: driver.find_element(By.ID, "xiaoluo-input").get_attribute("value") == "暂存的文字草稿")
        hear("讲解当前步骤")
        state("speaking")
        payload = js("return window.__voiceTest.requests.at(-1)")
        assert payload["context"] == {"type": "solution_step", "question_id": 42, "step_no": 2}, payload
        assert driver.find_element(By.ID, "xiaoluo-input").get_attribute("value") == "暂存的文字草稿"
        js("window.__voiceTest.ttsError('network')")
        assert "Huihui" in js("return window.__voiceTest.spoken.at(-1).voice")
        finish()

        js("window.__voiceTest.failure = 'chat'")
        before = count()
        hear("测试回答失败")
        wait.until(lambda _: count() == before + 1)
        state("listening")
        assert "未完成" in driver.find_element(By.CSS_SELECTOR, ".voice-notice").text

        # A disabled session must not speak a pending response.
        js("window.__voiceTest.holdReply = true")
        hear("测试延迟回答")
        state("thinking")
        click(".voice-toggle")
        state("off")
        spoken = js("return window.__voiceTest.spoken.length")
        js("window.__voiceTest.holdReply = false; window.__voiceTest.releaseReply()")
        wait.until(lambda _: not driver.find_element(By.ID, "xiaoluo-input").get_attribute("disabled"))
        assert js("return window.__voiceTest.spoken.length") == spoken
        assert js("return localStorage.getItem('xiaoluo_voice')") == "0"

        # Typing, quick prompts and history remain usable after voice is disabled.
        click(".chat-form button")
        wait.until(lambda _: not driver.find_element(By.ID, "xiaoluo-input").get_attribute("disabled"))
        assert js("return window.__voiceTest.requests.at(-1).message") == "暂存的文字草稿"
        before = count()
        click(".quick-row button")
        wait.until(lambda _: count() == before + 1)
        wait.until(lambda _: not driver.find_element(By.ID, "xiaoluo-input").get_attribute("disabled"))
        click(".drawer-actions button:nth-child(2)")
        wait.until(lambda _: driver.find_element(By.CSS_SELECTOR, ".history-box").is_displayed())
        click(".history-box > button")
        wait.until(lambda _: "历史对话仍可查看" in driver.find_element(By.CSS_SELECTOR, ".message-list").text)

        click(".voice-toggle")
        state("wake")
        driver.refresh()
        state("wake")
        hear("你好小逻")
        state("speaking")
        finish()
        js("window.__voiceTest.idle()")
        state("wake")
        js("window.__voiceTest.error('not-allowed')")
        state("error-permission")
        assert js("return localStorage.getItem('xiaoluo_voice')") == "0"
        click(".voice-status button")
        state("wake")
        js("window.__voiceTest.error('network')")
        state("error-network")

        for width, height in [(1440, 1000), (768, 1024), (375, 812), (320, 700)]:
            driver.set_window_size(width, height)
            # Match viewport dimensions, not browser outer dimensions.
            driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
                "width": width, "height": height, "deviceScaleFactor": 1, "mobile": False
            })
            click(".drawer-actions button:nth-child(2)")
            healthy_layout()
            driver.save_screenshot(str(OUTPUT / f"voice-history-{width}.png"))
            click(".drawer-actions button:nth-child(2)")

        driver.get(base + "/assignments?voiceRole=student")
        wait.until(lambda _: js("return !!document.querySelector('.assistant-drawer.is-open')"))
        state("off")
        click(".voice-toggle")
        state("wake")
        hear("你好小逻")
        state("speaking")
        finish()
        hear("请讲解数学函数")
        state("speaking")
        finish()
        for width, height in [(1440, 1000), (375, 812), (320, 700)]:
            driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
                "width": width, "height": height, "deviceScaleFactor": 1, "mobile": False
            })
            click(".drawer-actions button:nth-child(2)")
            healthy_layout()
            driver.save_screenshot(str(OUTPUT / f"voice-student-{width}.png"))
            click(".drawer-actions button:nth-child(2)")
        click(".voice-toggle")
        state("off")

        # Unsupported browsers hide voice only; text chat remains operational.
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": """
          Object.defineProperty(window, 'SpeechRecognition', {value: undefined, configurable:true});
          Object.defineProperty(window, 'webkitSpeechRecognition', {value: undefined, configurable:true});
        """})
        driver.refresh()
        wait.until(lambda _: js("return !!document.querySelector('.assistant-drawer.is-open')"))
        assert not driver.find_elements(By.CSS_SELECTOR, ".voice-toggle")
        assert driver.find_element(By.ID, "xiaoluo-input").is_enabled()
        severe = [item for item in driver.get_log("browser") if item["level"] == "SEVERE"]
        assert not severe, severe
        report["simulated_flow"] = "PASS"
        report["viewports"] = [1440, 768, 375, 320]
        report["real_microphone_test"] = "not performed; simulation cannot verify recognition accuracy or audible playback"
        (OUTPUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print("VOICE_BROWSER_OK " + json.dumps(report, ensure_ascii=False))
    except Exception:
        try:
            driver.save_screenshot(str(OUTPUT / "failed.png"))
            print("VOICE_BROWSER_FAILURE " + json.dumps(js("return {state:document.querySelector('.voice-status')?.textContent, spoken:window.__voiceTest?.spoken, requests:window.__voiceTest?.requests}"), ensure_ascii=False))
        except Exception:
            pass
        raise
    finally:
        driver.quit()
        if server:
            server.shutdown()


if __name__ == "__main__":
    main()
