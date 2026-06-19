/// MBclaw Mother Body — HTTP API 路由

use crate::auth::AuthService;
use crate::db::Database;
use crate::proxy::LLMProxy;
use axum::{
    extract::State,
    http::StatusCode,
    response::Json,
    routing::{get, post},
    Router,
};
use serde_json::{json, Value};
use std::sync::Arc;

pub struct AppState {
    pub db: Arc<Database>,
    pub auth: AuthService,
    pub proxy: LLMProxy,
}

pub fn create_router(state: Arc<AppState>) -> Router {
    Router::new()
        // 健康检查
        .route("/health", get(health))
        // 用户认证
        .route("/v1/auth/login", post(login))
        .route("/v1/auth/status", get(status))
        .route("/v1/auth/opt-out", post(opt_out))
        .route("/v1/auth/opt-in", post(opt_in))
        // LLM 代理
        .route("/v1/chat/completions", post(chat_completions))
        .route("/v1/models", get(list_models))
        // WebUI (登录页面)
        .route("/", get(webui))
        .with_state(state)
}

async fn health(State(state): State<Arc<AppState>>) -> Json<Value> {
    let users = state.db.user_count().await.unwrap_or(0);
    let opt_in = state.db.opt_in_count().await.unwrap_or(0);

    Json(json!({
        "status": "ok",
        "service": "MBclaw Mother Body",
        "version": "0.1.0",
        "users": users,
        "opt_in_users": opt_in,
        "timestamp": chrono::Utc::now().to_rfc3339(),
    }))
}

async fn login(
    State(state): State<Arc<AppState>>,
    Json(body): Json<Value>,
) -> Result<Json<Value>, (StatusCode, Json<Value>)> {
    let xiaomi_id = body.get("xiaomi_id")
        .and_then(|v| v.as_str())
        .ok_or_else(|| error_response(400, "Missing xiaomi_id"))?;
    let password = body.get("password")
        .and_then(|v| v.as_str())
        .ok_or_else(|| error_response(400, "Missing password"))?;

    match state.auth.login_password(xiaomi_id, password).await {
        Ok(resp) => Ok(Json(json!({
            "success": true,
            "user_id": resp.user_id,
            "nick": resp.nick,
            "session_token": resp.session_token,
            "message": "登录成功！已加入乌托邦计划。你可以在设置中随时关闭 token 贡献。"
        }))),
        Err(e) => Err(error_response(401, &e)),
    }
}

async fn status(
    State(state): State<Arc<AppState>>,
    Json(body): Json<Value>,
) -> Result<Json<Value>, (StatusCode, Json<Value>)> {
    let user_id = body.get("user_id")
        .and_then(|v| v.as_str())
        .ok_or_else(|| error_response(400, "Missing user_id"))?;

    match state.auth.get_status(user_id).await {
        Ok(status) => Ok(Json(json!({
            "user_id": status.user_id,
            "xiaomi_id": status.xiaomi_id,
            "nick": status.nick,
            "opt_in": status.opt_in,
            "today_usage": status.today_usage,
            "created_at": status.created_at,
            "benefits": if status.opt_in {
                ["完整MBclaw功能", "母体智能帮助", "公共知识库", "新功能优先体验"]
            } else {
                ["基础MBclaw功能"]
            }
        }))),
        Err(e) => Err(error_response(404, &e)),
    }
}

async fn opt_out(
    State(state): State<Arc<AppState>>,
    Json(body): Json<Value>,
) -> Result<Json<Value>, (StatusCode, Json<Value>)> {
    let user_id = body.get("user_id")
        .and_then(|v| v.as_str())
        .ok_or_else(|| error_response(400, "Missing user_id"))?;

    state.auth.set_opt_in(user_id, false).await.map_err(|e| error_response(500, &e))?;

    Ok(Json(json!({
        "success": true,
        "opt_in": false,
        "message": "已退出乌托邦计划。你将只能使用基础MBclaw功能，无法获得母体帮助。"
    })))
}

async fn opt_in(
    State(state): State<Arc<AppState>>,
    Json(body): Json<Value>,
) -> Result<Json<Value>, (StatusCode, Json<Value>)> {
    let user_id = body.get("user_id")
        .and_then(|v| v.as_str())
        .ok_or_else(|| error_response(400, "Missing user_id"))?;

    state.auth.set_opt_in(user_id, true).await.map_err(|e| error_response(500, &e))?;

    Ok(Json(json!({
        "success": true,
        "opt_in": true,
        "message": "已加入乌托邦计划！欢迎回来。"
    })))
}

async fn chat_completions(
    State(state): State<Arc<AppState>>,
    Json(body): Json<Value>,
) -> Result<Json<Value>, (StatusCode, Json<Value>)> {
    match state.proxy.chat_completions(body).await {
        Ok(resp) => Ok(Json(resp)),
        Err(e) => {
            if e == "token_expired" {
                Err(error_response(401, "Token expired, please re-login"))
            } else if e.contains("No opt-in") {
                Err(error_response(503, "No users available in the pool"))
            } else {
                Err(error_response(500, &e))
            }
        }
    }
}

async fn list_models(State(state): State<Arc<AppState>>) -> Json<Value> {
    Json(state.proxy.list_models())
}

/// 简单 WebUI 登录页面
async fn webui() -> (StatusCode, [(String, String); 1], String) {
    let html = r#"<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MBclaw — 乌托邦计划</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            color: #e0e0e0;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container {
            background: rgba(255,255,255,0.05);
            border-radius: 16px;
            padding: 40px;
            max-width: 400px;
            width: 90%;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
        }
        h1 {
            text-align: center;
            font-size: 28px;
            margin-bottom: 8px;
            background: linear-gradient(135deg, #7c3aed, #3b82f6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .subtitle {
            text-align: center;
            color: #94a3b8;
            font-size: 13px;
            margin-bottom: 24px;
        }
        .field {
            margin-bottom: 16px;
        }
        label {
            display: block;
            margin-bottom: 6px;
            font-size: 13px;
            color: #94a3b8;
        }
        input {
            width: 100%;
            padding: 12px;
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.15);
            border-radius: 8px;
            color: #e0e0e0;
            font-size: 15px;
            outline: none;
            transition: border 0.2s;
        }
        input:focus { border-color: #7c3aed; }
        button {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #7c3aed, #3b82f6);
            border: none;
            border-radius: 8px;
            color: white;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            margin-top: 8px;
            transition: opacity 0.2s;
        }
        button:hover { opacity: 0.9; }
        .info {
            margin-top: 20px;
            padding: 16px;
            background: rgba(124,58,237,0.1);
            border-radius: 8px;
            font-size: 12px;
            line-height: 1.6;
            color: #a78bfa;
        }
        .info strong { color: #c4b5fd; }
        #status { margin-top: 12px; text-align: center; font-size: 13px; min-height: 20px; }
        .error { color: #f87171; }
        .success { color: #4ade80; }
    </style>
</head>
<body>
    <div class="container">
        <h1>MBclaw</h1>
        <p class="subtitle">乌托邦计划 · 登录 miclaw 账号</p>
        <form id="loginForm">
            <div class="field">
                <label>Xiaomi 账号 (手机号/邮箱)</label>
                <input type="text" id="xiaomi_id" placeholder="miclaw 内测账号" required>
            </div>
            <div class="field">
                <label>密码</label>
                <input type="password" id="password" placeholder="Xiaomi 账号密码" required>
            </div>
            <button type="submit">登录并加入乌托邦</button>
        </form>
        <div id="status"></div>
        <div class="info">
            <strong>🌐 乌托邦计划</strong><br>
            登录即默认加入。你的 miclaw token 每天会随机被使用 0.1%-1%
            用于改善系统和母体智能。可随时在设置中关闭。<br><br>
            <strong>关闭后将无法获得母体帮助。</strong>
        </div>
    </div>
    <script>
        document.getElementById('loginForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const status = document.getElementById('status');
            status.textContent = '正在登录...';
            status.className = '';
            try {
                const resp = await fetch('/v1/auth/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        xiaomi_id: document.getElementById('xiaomi_id').value,
                        password: document.getElementById('password').value
                    })
                });
                const data = await resp.json();
                if (data.success) {
                    status.textContent = '✅ ' + data.message;
                    status.className = 'success';
                } else {
                    status.textContent = '❌ ' + (data.message || data.error || '登录失败');
                    status.className = 'error';
                }
            } catch (err) {
                status.textContent = '❌ 网络错误';
                status.className = 'error';
            }
        });
    </script>
</body>
</html>"#;

    (StatusCode::OK, [("Content-Type".to_string(), "text/html; charset=utf-8".to_string())], html.to_string())
}

fn error_response(code: u16, msg: &str) -> (StatusCode, Json<Value>) {
    (StatusCode::from_u16(code).unwrap_or(StatusCode::INTERNAL_SERVER_ERROR),
     Json(json!({"error": msg})))
}
