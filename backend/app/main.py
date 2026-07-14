from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from .api.routes.auth import router as auth_router
from .api.routes.learning import router as learning_router


app = FastAPI(
    title="行测智脑 API",
    description="基于多智能体协作的公考全科个性化导航系统",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "null",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(learning_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "message": "行测智脑 API 已启动",
        "docs": "/docs",
    }


@app.get("/docs", include_in_schema=False)
async def offline_docs() -> HTMLResponse:
    return HTMLResponse(
        """
        <!doctype html>
        <html lang="zh-CN">
        <head>
          <meta charset="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1" />
          <title>行测智脑 API 文档</title>
          <style>
            * { box-sizing: border-box; }
            body {
              margin: 0;
              min-height: 100vh;
              font-family: "Microsoft YaHei", "PingFang SC", Arial, sans-serif;
              color: #eaf6ff;
              background:
                radial-gradient(circle at 80% 10%, rgba(34, 211, 238, .18), transparent 30%),
                linear-gradient(135deg, #07172f, #0b2345 46%, #06101f);
            }
            main {
              width: min(1040px, calc(100% - 40px));
              margin: 0 auto;
              padding: 56px 0;
            }
            .hero, .endpoint {
              border: 1px solid rgba(160, 216, 255, .2);
              border-radius: 18px;
              background: rgba(8, 29, 58, .72);
              box-shadow: inset 0 1px 0 rgba(255,255,255,.12), 0 24px 90px rgba(0, 10, 30, .28);
              backdrop-filter: blur(18px);
            }
            .hero {
              padding: 30px;
              margin-bottom: 18px;
            }
            h1 { margin: 0 0 10px; font-size: 30px; }
            p { margin: 0; color: #acd8ee; line-height: 1.7; }
            .grid {
              display: grid;
              gap: 14px;
            }
            .endpoint {
              display: grid;
              grid-template-columns: 100px 1fr auto;
              gap: 16px;
              align-items: center;
              padding: 18px 20px;
            }
            .method {
              display: inline-flex;
              justify-content: center;
              padding: 8px 10px;
              border-radius: 999px;
              color: #082032;
              background: #7dd3fc;
              font-weight: 700;
            }
            code {
              color: #eaf6ff;
              font-size: 15px;
            }
            a {
              color: #8be9ff;
              text-decoration: none;
              font-weight: 700;
            }
            .hint {
              margin-top: 18px;
              padding: 16px 18px;
              border-radius: 16px;
              color: #c6e8f7;
              background: rgba(34, 211, 238, .1);
              border: 1px solid rgba(34, 211, 238, .2);
            }
            @media (max-width: 720px) {
              .endpoint {
                grid-template-columns: 1fr;
              }
            }
          </style>
        </head>
        <body>
          <main>
            <section class="hero">
              <h1>行测智脑 API 文档</h1>
              <p>后端服务已启动。当前页面是离线文档，不依赖 Swagger CDN，适合本地网络受限时验证接口。</p>
            </section>

            <section class="grid">
              <div class="endpoint">
                <span class="method">GET</span>
                <code>/api/health</code>
                <a href="/api/health">打开</a>
              </div>
              <div class="endpoint">
                <span class="method">POST</span>
                <code>/api/login</code>
                <span>用户名密码登录</span>
              </div>
              <div class="endpoint">
                <span class="method">POST</span>
                <code>/api/register</code>
                <span>注册新用户，密码哈希入库</span>
              </div>
              <div class="endpoint">
                <span class="method">GET</span>
                <code>/api/diagnose?user_id=1</code>
                <a href="/api/diagnose?user_id=1">打开</a>
              </div>
              <div class="endpoint">
                <span class="method">GET</span>
                <code>/api/recommend</code>
                <a href="/api/recommend">打开</a>
              </div>
              <div class="endpoint">
                <span class="method">GET</span>
                <code>/api/score-lines</code>
                <a href="/api/score-lines">打开</a>
              </div>
              <div class="endpoint">
                <span class="method">GET</span>
                <code>/api/user-goals?user_id=1</code>
                <a href="/api/user-goals?user_id=1">打开</a>
              </div>
              <div class="endpoint">
                <span class="method">POST</span>
                <code>/api/user-goals</code>
                <span>保存目标分数和考试日期</span>
              </div>
              <div class="endpoint">
                <span class="method">GET</span>
                <code>/api/question-types</code>
                <a href="/api/question-types">打开</a>
              </div>
              <div class="endpoint">
                <span class="method">GET</span>
                <code>/api/practice/random</code>
                <a href="/api/practice/random?limit=5">打开</a>
              </div>
              <div class="endpoint">
                <span class="method">GET</span>
                <code>/api/mock-exam</code>
                <a href="/api/mock-exam?limit=20">打开</a>
              </div>
              <div class="endpoint">
                <span class="method">POST</span>
                <code>/api/practice/submit</code>
                <span>提交答案并写入做题记录</span>
              </div>
              <div class="endpoint">
                <span class="method">GET</span>
                <code>/api/study-plans/options</code>
                <a href="/api/study-plans/options">打开</a>
              </div>
              <div class="endpoint">
                <span class="method">POST</span>
                <code>/api/study-plans/select</code>
                <span>保存用户备考方案</span>
              </div>
              <div class="endpoint">
                <span class="method">POST</span>
                <code>/api/chat</code>
                <span>text/event-stream</span>
              </div>
              <div class="endpoint">
                <span class="method">GET</span>
                <code>/api/chat/history?user_id=1</code>
                <a href="/api/chat/history?user_id=1">打开</a>
              </div>
              <div class="endpoint">
                <span class="method">GET</span>
                <code>/api/chat/sessions?user_id=1</code>
                <a href="/api/chat/sessions?user_id=1">打开</a>
              </div>
              <div class="endpoint">
                <span class="method">JSON</span>
                <code>/openapi.json</code>
                <a href="/openapi.json">打开</a>
              </div>
            </section>

            <div class="hint">
              如果你一定要原版 Swagger UI，需要浏览器能加载 Swagger 的外部 CDN 资源；否则默认 Swagger 页面可能白屏。
            </div>
          </main>
        </body>
        </html>
        """
    )
