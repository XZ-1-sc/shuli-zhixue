from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from .api.routes.auth import router as auth_router
from .api.routes.assignments import router as assignments_router
from .api.routes.learning import router as learning_router
from .api.routes.teacher import router as teacher_router
from .api.routes.teacher_workflow import router as teacher_workflow_router
from .api.routes.uploads import router as uploads_router


app = FastAPI(
    title="数理智学 API",
    description="面向本科大学数学的智能学习诊断、规划、刷题与复盘系统。",
    version="0.2.0",
    docs_url=None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "null",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(learning_router)
app.include_router(uploads_router)
app.include_router(teacher_router)
app.include_router(teacher_workflow_router)
app.include_router(assignments_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "数理智学 API 已启动", "docs": "/docs"}


@app.get("/docs", include_in_schema=False)
async def offline_docs() -> HTMLResponse:
    endpoints = [
        ("GET", "/api/health", "健康检查"),
        ("POST", "/api/register", "注册用户，密码哈希入库"),
        ("POST", "/api/login", "登录用户"),
        ("GET", "/api/stages", "学习阶段与课程"),
        ("GET", "/api/courses?stage=大一", "按阶段查询课程"),
        ("GET", "/api/knowledge-graph", "数学知识图谱"),
        ("GET", "/api/question-types", "题型与知识点统计"),
        ("GET", "/api/practice/random", "随机抽题"),
        ("POST", "/api/practice/submit", "提交答案并返回解析"),
        ("POST", "/api/uploads/answer-images", "上传作答图片"),
        ("POST", "/api/uploads/note-files", "上传笔记图片或文件"),
        ("POST", "/api/assessment/start", "开始或继续基础首测"),
        ("GET", "/api/diagnose", "当前会话账号的学习诊断"),
        ("GET", "/api/recommend", "当前会话账号的今日练习推荐"),
        ("GET", "/api/study-roadmap", "当前会话账号的完整学习规划"),
        ("GET", "/api/review/wrong-questions", "当前会话账号的错题复盘"),
        ("GET", "/api/messages", "当前会话账号的消息中心"),
        ("GET", "/api/profile/summary", "当前会话账号的学习档案"),
        ("GET", "/api/achievements", "当前会话账号的成就徽章"),
        ("GET", "/api/resources", "课程资源"),
        ("GET", "/api/notes", "当前会话账号的笔记列表"),
        ("POST", "/api/notes", "新增笔记"),
        ("PUT", "/api/notes/{note_id}", "编辑笔记"),
        ("DELETE", "/api/notes/{note_id}", "删除笔记"),
        ("POST", "/api/chat", "小逻流式对话"),
        ("GET", "/api/chat/history", "当前会话账号的对话历史"),
        ("JSON", "/openapi.json", "OpenAPI JSON"),
    ]
    endpoint_html = "\n".join(
        f"""
        <div class="endpoint">
          <span class="method">{method}</span>
          <code>{path}</code>
          <span>{desc}</span>
        </div>
        """
        for method, path, desc in endpoints
    )
    return HTMLResponse(
        f"""
        <!doctype html>
        <html lang="zh-CN">
        <head>
          <meta charset="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1" />
          <title>数理智学 API 文档</title>
          <style>
            * {{ box-sizing: border-box; }}
            body {{
              margin: 0;
              min-height: 100vh;
              font-family: "Microsoft YaHei", "PingFang SC", Arial, sans-serif;
              color: #f4f0e8;
              background:
                radial-gradient(circle at 78% 12%, rgba(72, 210, 224, .14), transparent 34%),
                linear-gradient(135deg, #071015, #111923 52%, #090c10);
            }}
            main {{
              width: min(1080px, calc(100% - 40px));
              margin: 0 auto;
              padding: 56px 0;
            }}
            .hero, .endpoint {{
              border: 1px solid rgba(188, 204, 209, .18);
              border-radius: 18px;
              background: rgba(18, 28, 36, .78);
              box-shadow: inset 0 1px 0 rgba(255,255,255,.08), 0 24px 90px rgba(0, 0, 0, .34);
            }}
            .hero {{
              padding: 30px;
              margin-bottom: 18px;
            }}
            h1 {{ margin: 0 0 10px; font-size: 34px; letter-spacing: 0; }}
            p {{ margin: 0; color: #b9c8ca; line-height: 1.7; }}
            .grid {{ display: grid; gap: 14px; }}
            .endpoint {{
              display: grid;
              grid-template-columns: 92px minmax(220px, 1fr) minmax(180px, .8fr);
              gap: 16px;
              align-items: center;
              padding: 18px 20px;
            }}
            .method {{
              display: inline-flex;
              justify-content: center;
              padding: 8px 10px;
              border-radius: 999px;
              color: #061317;
              background: #64d7e8;
              font-weight: 800;
            }}
            code {{ color: #fff8ec; font-size: 15px; }}
            @media (max-width: 720px) {{
              .endpoint {{ grid-template-columns: 1fr; }}
            }}
          </style>
        </head>
        <body>
          <main>
            <section class="hero">
              <h1>数理智学 API 文档</h1>
              <p>当前后端已切换到 math_brain 数据库，用于本科大学数学阶段诊断、刷题、规划、知识图谱和错题复盘。</p>
            </section>
            <section class="grid">{endpoint_html}</section>
          </main>
        </body>
        </html>
        """
    )
