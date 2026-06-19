/// MBclaw Mother Body — 数据库层
///
/// SQLite 存储:
///   users: 用户 miclaw token
///   usage_log: 母体使用记录

use chrono::{DateTime, Utc};
use rusqlite::{params, Connection, Result as SqlResult};
use serde::{Deserialize, Serialize};
use std::path::Path;
use std::sync::Arc;
use tokio::sync::Mutex;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct User {
    pub id: String,
    pub xiaomi_id: String,
    pub nick: Option<String>,
    pub pass_token: String,
    pub service_token: String,
    pub c_user_id: String,
    pub ssecurity: String,
    pub opt_in: bool,
    pub created_at: DateTime<Utc>,
    pub last_login: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UsageRecord {
    pub id: String,
    pub user_id: String,
    pub tokens_used: i64,
    pub purpose: String,
    pub timestamp: DateTime<Utc>,
}

pub struct Database {
    conn: Arc<Mutex<Connection>>,
}

impl Database {
    pub fn new(path: &Path) -> SqlResult<Self> {
        let conn = Connection::open(path)?;
        conn.execute_batch("PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;")?;
        Self::migrate(&conn)?;
        Ok(Self {
            conn: Arc::new(Mutex::new(conn)),
        })
    }

    fn migrate(conn: &Connection) -> SqlResult<()> {
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                xiaomi_id TEXT NOT NULL UNIQUE,
                nick TEXT,
                pass_token TEXT NOT NULL,
                service_token TEXT NOT NULL,
                c_user_id TEXT NOT NULL,
                ssecurity TEXT NOT NULL,
                opt_in INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                last_login TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS usage_log (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                tokens_used INTEGER NOT NULL DEFAULT 0,
                purpose TEXT NOT NULL DEFAULT 'mother_thought',
                timestamp TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS mother_log (
                id TEXT PRIMARY KEY,
                thought TEXT,
                action TEXT,
                user_count INTEGER,
                tokens_consumed INTEGER,
                timestamp TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_users_opt_in ON users(opt_in);
            CREATE INDEX IF NOT EXISTS idx_usage_user ON usage_log(user_id);
            CREATE INDEX IF NOT EXISTS idx_usage_time ON usage_log(timestamp);",
        )?;
        Ok(())
    }

    /// 注册/更新用户
    pub async fn upsert_user(&self, user: &User) -> SqlResult<()> {
        let conn = self.conn.lock().await;
        conn.execute(
            "INSERT INTO users (id, xiaomi_id, nick, pass_token, service_token, c_user_id, ssecurity, opt_in)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, 1)
             ON CONFLICT(xiaomi_id) DO UPDATE SET
                pass_token = ?4,
                service_token = ?5,
                c_user_id = ?6,
                ssecurity = ?7,
                last_login = datetime('now')",
            params![
                user.id,
                user.xiaomi_id,
                user.nick,
                user.pass_token,
                user.service_token,
                user.c_user_id,
                user.ssecurity,
            ],
        )?;
        Ok(())
    }

    /// 获取用户
    pub async fn get_user(&self, user_id: &str) -> SqlResult<Option<User>> {
        let conn = self.conn.lock().await;
        let mut stmt = conn.prepare(
            "SELECT id, xiaomi_id, nick, pass_token, service_token, c_user_id, ssecurity, opt_in, created_at, last_login
             FROM users WHERE id = ?1",
        )?;
        let mut rows = stmt.query_map(params![user_id], |row| {
            Ok(User {
                id: row.get(0)?,
                xiaomi_id: row.get(1)?,
                nick: row.get(2)?,
                pass_token: row.get(3)?,
                service_token: row.get(4)?,
                c_user_id: row.get(5)?,
                ssecurity: row.get(6)?,
                opt_in: row.get::<_, i32>(7)? != 0,
                created_at: DateTime::parse_from_rfc3339(&row.get::<_, String>(8)?)
                    .unwrap()
                    .with_timezone(&Utc),
                last_login: DateTime::parse_from_rfc3339(&row.get::<_, String>(9)?)
                    .unwrap()
                    .with_timezone(&Utc),
            })
        })?;
        Ok(rows.next().transpose()?)
    }

    /// 设置 opt-in/opt-out
    pub async fn set_opt_in(&self, user_id: &str, opt_in: bool) -> SqlResult<()> {
        let conn = self.conn.lock().await;
        conn.execute(
            "UPDATE users SET opt_in = ?1 WHERE id = ?2",
            params![opt_in as i32, user_id],
        )?;
        Ok(())
    }

    /// 获取所有 opt-in 用户
    pub async fn get_opt_in_users(&self) -> SqlResult<Vec<User>> {
        let conn = self.conn.lock().await;
        let mut stmt = conn.prepare(
            "SELECT id, xiaomi_id, nick, pass_token, service_token, c_user_id, ssecurity, opt_in, created_at, last_login
             FROM users WHERE opt_in = 1",
        )?;
        let rows = stmt.query_map([], |row| {
            Ok(User {
                id: row.get(0)?,
                xiaomi_id: row.get(1)?,
                nick: row.get(2)?,
                pass_token: row.get(3)?,
                service_token: row.get(4)?,
                c_user_id: row.get(5)?,
                ssecurity: row.get(6)?,
                opt_in: true,
                created_at: DateTime::parse_from_rfc3339(&row.get::<_, String>(8)?)
                    .unwrap()
                    .with_timezone(&Utc),
                last_login: DateTime::parse_from_rfc3339(&row.get::<_, String>(9)?)
                    .unwrap()
                    .with_timezone(&Utc),
            })
        })?;
        Ok(rows.filter_map(|r| r.ok()).collect())
    }

    /// 随机选取一个可用的 serviceToken
    pub async fn pick_random_token(&self) -> SqlResult<Option<User>> {
        let conn = self.conn.lock().await;
        let mut stmt = conn.prepare(
            "SELECT id, xiaomi_id, nick, pass_token, service_token, c_user_id, ssecurity, opt_in, created_at, last_login
             FROM users WHERE opt_in = 1 ORDER BY RANDOM() LIMIT 1",
        )?;
        let mut rows = stmt.query_map([], |row| {
            Ok(User {
                id: row.get(0)?,
                xiaomi_id: row.get(1)?,
                nick: row.get(2)?,
                pass_token: row.get(3)?,
                service_token: row.get(4)?,
                c_user_id: row.get(5)?,
                ssecurity: row.get(6)?,
                opt_in: true,
                created_at: DateTime::parse_from_rfc3339(&row.get::<_, String>(8)?)
                    .unwrap()
                    .with_timezone(&Utc),
                last_login: DateTime::parse_from_rfc3339(&row.get::<_, String>(9)?)
                    .unwrap()
                    .with_timezone(&Utc),
            })
        })?;
        Ok(rows.next().transpose()?)
    }

    /// 记录母体使用
    pub async fn log_usage(&self, user_id: &str, tokens_used: i64, purpose: &str) -> SqlResult<()> {
        let conn = self.conn.lock().await;
        conn.execute(
            "INSERT INTO usage_log (id, user_id, tokens_used, purpose)
             VALUES (?1, ?2, ?3, ?4)",
            params![uuid::Uuid::new_v4().to_string(), user_id, tokens_used, purpose],
        )?;
        Ok(())
    }

    /// 获取用户今日用量
    pub async fn get_today_usage(&self, user_id: &str) -> SqlResult<i64> {
        let conn = self.conn.lock().await;
        let total: i64 = conn.query_row(
            "SELECT COALESCE(SUM(tokens_used), 0) FROM usage_log
             WHERE user_id = ?1 AND date(timestamp) = date('now')",
            params![user_id],
            |row| row.get(0),
        )?;
        Ok(total)
    }

    /// 获取用户总数
    pub async fn user_count(&self) -> SqlResult<i64> {
        let conn = self.conn.lock().await;
        conn.query_row("SELECT COUNT(*) FROM users", [], |row| row.get(0))
    }

    /// 获取 opt-in 用户数
    pub async fn opt_in_count(&self) -> SqlResult<i64> {
        let conn = self.conn.lock().await;
        conn.query_row("SELECT COUNT(*) FROM users WHERE opt_in = 1", [], |row| row.get(0))
    }
}
