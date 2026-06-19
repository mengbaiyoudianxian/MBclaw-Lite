/// MBclaw Mother Body — 乌托邦计划云端服务入口
///
/// 功能:
///   - Xiaomi OAuth 登录 (多用户)
///   - miclaw token 池管理
///   - OpenAI 兼容 LLM 代理 (随机 token 调度)
///   - 母体智能体调度器
///   - WebUI 登录页面

mod api;
mod auth;
mod db;
mod proxy;

use crate::api::AppState;
use crate::auth::AuthService;
use crate::db::Database;
use crate::proxy::LLMProxy;
use std::path::PathBuf;
use std::sync::Arc;
use tracing::info;
use tracing_subscriber::EnvFilter;

#[tokio::main]
async fn main() {
    // Init logging
    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| EnvFilter::new("info")),
        )
        .init();

    // Init database
    let db_path = std::env::var("DATABASE_URL")
        .unwrap_or_else(|_| "data/mother.db".to_string());
    let db_path = PathBuf::from(&db_path);
    if let Some(parent) = db_path.parent() {
        std::fs::create_dir_all(parent).ok();
    }

    let db = Database::new(&db_path).expect("Failed to open database");
    let db = Arc::new(db);

    info!("Database: {}", db_path.display());
    info!("Users: {}", db.user_count().await.unwrap_or(0));
    info!("Opt-in: {}", db.opt_in_count().await.unwrap_or(0));

    // Init services
    let auth = AuthService::new(db.clone());
    let proxy = LLMProxy::new(db.clone());

    let state = Arc::new(AppState { db, auth, proxy });

    // Build router
    let app = api::create_router(state);

    // Bind
    let host = std::env::var("HOST").unwrap_or_else(|_| "0.0.0.0".to_string());
    let port: u16 = std::env::var("PORT")
        .unwrap_or_else(|_| "8765".to_string())
        .parse()
        .unwrap_or(8765);

    let addr = format!("{host}:{port}");
    info!("MBclaw Mother Body starting on http://{addr}");

    let listener = tokio::net::TcpListener::bind(&addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
