/// MBclaw Mother Body — LLM 代理
///
/// 随机从 token 池中选取 serviceToken，转发 LLM 请求到 miclaw API

use crate::db::Database;
use reqwest::Client;
use serde_json::Value;
use std::sync::Arc;
use tracing::{info, warn};

pub struct LLMProxy {
    db: Arc<Database>,
    client: Client,
    miclaw_api: String,
}

impl LLMProxy {
    pub fn new(db: Arc<Database>) -> Self {
        Self {
            db,
            client: Client::new(),
            miclaw_api: "https://api.miclaw.xiaomi.net/osbot/pc/llm/v1/chat/completions"
                .to_string(),
        }
    }

    /// 代理 chat/completions 请求
    /// 从 token 池随机选一个 opt-in 用户的 serviceToken 转发
    pub async fn chat_completions(&self, body: Value) -> Result<Value, String> {
        // 随机选取一个 opt-in 用户
        let user = self.db.pick_random_token()
            .await
            .map_err(|e| format!("DB error: {e}"))?
            .ok_or("No opt-in users available")?;

        info!(
            "Proxying request via user: {} (opt-in pool: {})",
            user.xiaomi_id,
            self.db.opt_in_count().await.unwrap_or(0)
        );

        let resp = self
            .client
            .post(&self.miclaw_api)
            .header("Content-Type", "application/json")
            .header(
                "Cookie",
                format!("serviceToken={}; cUserId={}", user.service_token, user.c_user_id),
            )
            .header("User-Agent", "node")
            .json(&body)
            .send()
            .await
            .map_err(|e| format!("API error: {e}"))?;

        let status = resp.status();
        let result: Value = resp.json().await.map_err(|e| format!("JSON: {e}"))?;

        if status == 401 {
            warn!("Token expired for user: {} — needs refresh", user.xiaomi_id);
            // Try another user
            return Err("token_expired".to_string());
        }

        // 估算 token 用量并记录
        let estimated_tokens = estimate_tokens(&body, &result);
        let _ = self.db.log_usage(&user.id, estimated_tokens, "chat_completion").await;

        Ok(result)
    }

    /// 返回可用模型列表
    pub fn list_models(&self) -> Value {
        serde_json::json!({
            "object": "list",
            "data": [
                {"id": "xiaomi/mimo", "object": "model", "owned_by": "xiaomi"},
                {"id": "xiaomi/mimo-pro", "object": "model", "owned_by": "xiaomi"},
                {"id": "xiaomi/mimo-claw-0301", "object": "model", "owned_by": "xiaomi"},
                {"id": "xiaomi/MiniMax-M2.5", "object": "model", "owned_by": "xiaomi"},
                {"id": "xiaomi/kimi-k2.5", "object": "model", "owned_by": "xiaomi"},
                {"id": "xiaomi/glm-5", "object": "model", "owned_by": "xiaomi"},
                {"id": "mimo-omni", "object": "model", "owned_by": "xiaomi"},
                {"id": "mimo-pro", "object": "model", "owned_by": "xiaomi"}
            ]
        })
    }
}

/// 粗略估算 token 用量
fn estimate_tokens(request: &Value, response: &Value) -> i64 {
    // 简单估算: 统计 usage 字段，或按字符数 / 4
    if let Some(usage) = response.get("usage") {
        if let Some(total) = usage.get("total_tokens").and_then(|v| v.as_i64()) {
            return total;
        }
    }
    // Fallback: 字符数估算
    let req_chars = request.to_string().len() as i64;
    let resp_chars = response.to_string().len() as i64;
    (req_chars + resp_chars) as i64 / 4
}
