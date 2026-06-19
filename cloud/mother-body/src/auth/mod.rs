/// MBclaw Mother Body — Xiaomi OAuth 认证
///
/// 基于 miclaw_api_bridge 的 OAuth 流程:
///   1. POST account.xiaomi.com/pass/serviceLoginAuth2 (sid=miclaw)
///      → 2FA if needed → passToken + cUserId + ssecurity
///   2. GET account.xiaomi.com/pass/serviceLogin?sid=osbotapi
///      → loc + nonce + ssecurity
///   3. GET <loc>&clientSign=<sig>
///      → serviceToken
///
/// 多用户改造: token 存入 SQLite users 表

use crate::db::{Database, User};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tracing::{info, warn, error};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LoginRequest {
    pub xiaomi_id: String,
    pub password: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LoginResponse {
    pub user_id: String,
    pub nick: Option<String>,
    pub session_token: String, // 内部 session，用于后续 API 调用
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UserStatus {
    pub user_id: String,
    pub xiaomi_id: String,
    pub nick: Option<String>,
    pub opt_in: bool,
    pub today_usage: i64,
    pub created_at: String,
}

pub struct AuthService {
    db: Arc<Database>,
    client: Client,
}

impl AuthService {
    pub fn new(db: Arc<Database>) -> Self {
        Self {
            db,
            client: Client::builder()
                .cookie_store(true)
                .build()
                .unwrap(),
        }
    }

    /// Step 1: Xiaomi password login → passToken
    pub async fn login_password(&self, xiaomi_id: &str, password: &str) -> Result<LoginResponse, String> {
        info!("Login: {xiaomi_id}");

        // Step 1: serviceLoginAuth2 (sid=miclaw)
        let pass_token = self.step1_password_auth(xiaomi_id, password).await?;

        // Step 2: serviceLogin (sid=osbotapi) → nonce + ssecurity
        let (loc, nonce, ssecurity, c_user_id) =
            self.step2_service_login(&pass_token, xiaomi_id).await?;

        // Step 3: clientSign → serviceToken
        let service_token = self.step3_client_sign(&loc, &nonce, &ssecurity).await?;

        // Store user
        let user = User {
            id: format!("u_{}", &xiaomi_id[..8.min(xiaomi_id.len())]),
            xiaomi_id: xiaomi_id.to_string(),
            nick: Some(xiaomi_id.split('@').next().unwrap_or(xiaomi_id).to_string()),
            pass_token,
            service_token,
            c_user_id,
            ssecurity,
            opt_in: true, // 默认 opt-in
            created_at: chrono::Utc::now(),
            last_login: chrono::Utc::now(),
        };

        let user_id = user.id.clone();
        let nick = user.nick.clone();
        self.db.upsert_user(&user).await.map_err(|e| e.to_string())?;

        info!("Login success: {user_id}");
        Ok(LoginResponse {
            user_id,
            nick,
            session_token: uuid::Uuid::new_v4().to_string(),
        })
    }

    /// Step 1: Password auth → passToken, cUserId, ssecurity
    async fn step1_password_auth(&self, user: &str, pass: &str) -> Result<String, String> {
        let pass_hash = format!("{:X}", md5::compute(pass.as_bytes()));

        let resp = self
            .client
            .post("https://account.xiaomi.com/pass/serviceLoginAuth2")
            .form(&[
                ("sid", "miclaw"),
                ("user", user),
                ("hash", &pass_hash),
                ("_json", "true"),
            ])
            .send()
            .await
            .map_err(|e| format!("Login request failed: {e}"))?;

        let body: serde_json::Value = resp.json().await.map_err(|e| format!("JSON parse: {e}"))?;

        // Check for 2FA
        if let Some(code) = body.get("code").and_then(|c| c.as_i64()) {
            if code == 81103 {
                return Err("2FA required — use WebUI login".to_string());
            }
        }

        // Extract passToken
        body.get("passToken")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string())
            .ok_or_else(|| {
                let desc = body.get("desc").and_then(|v| v.as_str()).unwrap_or("unknown");
                format!("Login failed: {desc}")
            })
    }

    /// Step 2: serviceLogin (sid=osbotapi) → loc, nonce, ssecurity
    async fn step2_service_login(
        &self,
        pass_token: &str,
        xiaomi_id: &str,
    ) -> Result<(String, String, String, String), String> {
        let c_user_id = xiaomi_id.to_string(); // simplified
        let device_id = format!("pc_{:x}", md5::compute("mbclaw-mother-body"));

        let resp = self
            .client
            .get("https://account.xiaomi.com/pass/serviceLogin")
            .query(&[
                ("sid", "osbotapi"),
                ("_json", "true"),
            ])
            .header("Cookie", format!(
                "passToken={}; userId={}; cUserId={}; deviceId={}",
                pass_token, xiaomi_id, c_user_id, device_id
            ))
            .header("User-Agent", "miNative PC/3.0.0")
            .send()
            .await
            .map_err(|e| format!("ServiceLogin failed: {e}"))?;

        let body: serde_json::Value = resp.json().await.map_err(|e| format!("JSON: {e}"))?;

        let loc = body.get("location")
            .and_then(|v| v.as_str())
            .ok_or("No location in response")?
            .to_string();

        let nonce = body.get("nonce")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string())
            .unwrap_or_default();

        let ssecurity = body.get("ssecurity")
            .and_then(|v| v.as_str())
            .ok_or("No ssecurity in response")?
            .to_string();

        Ok((loc, nonce, ssecurity, c_user_id))
    }

    /// Step 3: clientSign → serviceToken
    async fn step3_client_sign(&self, loc: &str, nonce: &str, ssecurity: &str) -> Result<String, String> {
        let sign_str = format!("nonce={nonce}&{ssecurity}");
        let sign_hash = sha1::Sha1::from(sign_str.as_bytes()).digest().to_string();
        let sign_encoded = urlencoding::encode(&base64::Engine::encode(
            &base64::engine::general_purpose::STANDARD,
            hex::decode(&sign_hash).map_err(|e| e.to_string())?,
        ));

        let sign_url = format!("{loc}&clientSign={sign_encoded}");

        let resp = self
            .client
            .get(&sign_url)
            .send()
            .await
            .map_err(|e| format!("ClientSign failed: {e}"))?;

        // Extract serviceToken from Set-Cookie
        for cookie in resp.headers().get_all("set-cookie") {
            if let Ok(cookie_str) = cookie.to_str() {
                if let Some(token) = cookie_str
                    .split(';')
                    .find(|c| c.trim().starts_with("serviceToken="))
                {
                    return Ok(token.trim().replace("serviceToken=", ""));
                }
            }
        }

        Err("No serviceToken in response".to_string())
    }

    /// 获取用户状态
    pub async fn get_status(&self, user_id: &str) -> Result<UserStatus, String> {
        let user = self.db.get_user(user_id).await.map_err(|e| e.to_string())?
            .ok_or("User not found")?;
        let today_usage = self.db.get_today_usage(user_id).await.unwrap_or(0);

        Ok(UserStatus {
            user_id: user.id,
            xiaomi_id: user.xiaomi_id,
            nick: user.nick,
            opt_in: user.opt_in,
            today_usage,
            created_at: user.created_at.to_rfc3339(),
        })
    }

    /// Opt-out / Opt-in
    pub async fn set_opt_in(&self, user_id: &str, opt_in: bool) -> Result<(), String> {
        self.db.set_opt_in(user_id, opt_in).await.map_err(|e| e.to_string())
    }
}
