# Email Agent

AI Gmail Assistant with Telegram Bot
使用 Python + Gmail API + Telegram Bot 打造的個人郵件整理助手。

---

# 功能介紹

這個專案可以幫你把 Gmail 郵件自動整理後推送到 Telegram，並支援手動指令操作。

目前支援功能：

## 1. 郵件整理摘要

* 抓取 Gmail 未讀郵件
* 使用 AI 進行郵件整理與摘要
* 將整理結果推送到 Telegram

## 2. Gmail 自動標籤

可依規則將郵件自動分類，例如：

* AI/一般
* AI/重要
* AI/可封存
* 銀行 / 金融相關標籤
* 登入通知 / 安全通知
* 廣告或可封存郵件

## 3. 智慧封存

* 預覽符合低風險封存條件的郵件
* 手動確認後再進行封存
* 避免重要郵件被直接清掉

## 4. Telegram 中文指令控制

支援直接在 Telegram 對 bot 下指令，不用每次都記英文。

## 5. 自動排程

台灣時間固定自動整理：

* 08:00
* 12:00
* 17:00
* 21:00

並且：

* 不會補跑過去日期的排程
* 同一個時段只執行一次
* 若 Gmail token 失效，會回報錯誤而不會無限重跑
* 若 Telegram timeout / DNS 失敗，bot 不會整個崩潰

---

# 專案結構

```bash
email-agent/
├─ actions.py               # 郵件封存 / 標籤邏輯
├─ ai_summary.py            # AI 郵件摘要整理
├─ bot.py                   # Telegram Bot 主程式 + 自動排程
├─ gmail_service.py         # Gmail API 讀信 / 標籤 / 封存操作
├─ mail_rules.py            # 郵件分類規則
├─ telegram_notify.py       # 發送 Telegram 訊息
├─ requirements.txt         # Python 套件需求
├─ token.json               # Gmail OAuth 授權 token（執行後產生）
├─ credentials.json         # Google Cloud OAuth 憑證（自行放入）
├─ .env                     # 環境變數（自行建立）
└─ bot_state.json           # 自動排程執行狀態（執行後產生）
```

---

# 安裝需求

* Python 3.11+（建議 3.12 / 3.13）
* Gmail 帳號
* Telegram 帳號
* Telegram Bot Token
* Google Cloud Gmail API OAuth 憑證
* OpenAI API Key（若有使用 AI 摘要功能）

---

# 安裝步驟

## 1. 下載專案

```bash
git clone https://github.com/zxc558857/email-agent.git
cd email-agent
```

## 2. 安裝套件

```bash
pip install -r requirements.txt
```

---

# 環境變數設定

請在專案根目錄建立 `.env` 檔案：

```env
TELEGRAM_BOT_TOKEN=你的TelegramBotToken
TELEGRAM_CHAT_ID=你的TelegramChatID
OPENAI_API_KEY=你的OpenAI_API_KEY
```

如果你的 `ai_summary.py` 還有其他模型參數，也可以一併放進 `.env`。

---

# Gmail API 設定

## 1. 建立 Google Cloud 專案

到 Google Cloud Console 建立專案，並啟用 Gmail API。

## 2. 建立 OAuth 憑證

建立 OAuth Client，下載 `credentials.json`，放到專案根目錄。

## 3. 第一次執行 bot

第一次執行時會跳出瀏覽器要求你授權 Gmail，完成後會自動產生：

```bash
token.json
```

之後 bot 就會使用 `token.json` 進行 Gmail 操作。

---

# Telegram Bot 設定

## 1. 建立 Bot

用 Telegram 的 BotFather 建立 bot，拿到 `TELEGRAM_BOT_TOKEN`

## 2. 取得 Chat ID

把 bot 拉進你的對話，傳送一則訊息後，透過 Telegram API 或其他方式取得 `TELEGRAM_CHAT_ID`

放進 `.env` 即可。

---

# 啟動方式

## 手動啟動

```bash
python bot.py
```

若成功啟動，終端機會看到：

```bash
AI Email Agent Bot started...
```

---

# 支援指令

## 郵件整理

以下任一指令都可觸發整理：

```text
整理
郵件整理
查看郵件
看郵件
信箱
gmail
幫我整理郵件
幫我看信箱
/summary
```

---

## 自動標籤

以下任一指令都可觸發 Gmail 自動分類：

```text
標籤
加標籤
分類
郵件分類
幫我分類
自動分類
/label
```

---

## 預覽可封存郵件

```text
封存
封存郵件
整理垃圾信
封存垃圾信
清垃圾信
清理郵件
清理信箱
/archive
```

---

## 確認封存

```text
確認
確定
YES
封存確認
確認封存
```

---

## 查看幫助

```text
幫助
指令
功能
怎麼用
使用說明
/help
/start
```

---

# 自動排程

系統會使用 **台灣時間 Asia/Taipei** 自動執行整理。

## 排程時間

* 08:00
* 12:00
* 17:00
* 21:00

## 排程機制說明

* 同一時段只執行一次
* 不補跑舊日期的排程
* 執行狀態會記錄在 `bot_state.json`
* 如果 Gmail token 失效，該次會標記為 failed，並發送錯誤訊息
* 如果 Telegram API timeout / DNS 失敗，bot 會繼續運作，不會整個停止

---

# bot_state.json 說明

執行過自動排程後，會在專案目錄產生：

```json
{
  "last_auto_run_key": "2026-06-25-08",
  "last_auto_run_started_at": "2026-06-25T08:00:01+08:00",
  "last_auto_run_status": "success",
  "last_auto_run_finished_at": "2026-06-25T08:00:12+08:00"
}
```

欄位說明：

* `last_auto_run_key`：最近一次排程的時段 key
* `last_auto_run_started_at`：開始執行時間
* `last_auto_run_status`：`running / success / failed`
* `last_auto_run_finished_at`：結束時間
* `last_auto_run_error`：若失敗會記錄錯誤訊息

---

# Windows 開機自動啟動（可選）

如果你想讓 bot 在自己電腦開機後自動啟動，可建立批次檔，例如：

## `start_email_agent.bat`

```bat
@echo off
cd /d C:\Users\user\Desktop\email-agent
python bot.py
pause
```

再把這個 `.bat` 放到 Windows 啟動資料夾，或用工作排程器執行。

---

# 常見錯誤排除

## 1. Gmail token 失效

若 Telegram 或終端機出現：

```text
invalid_grant
Token has been expired or revoked
```

請刪除專案中的：

```bash
token.json
```

然後重新執行：

```bash
python bot.py
```

依照瀏覽器流程重新授權 Gmail。

---

## 2. Telegram 發送失敗 / timeout / DNS 失敗

若終端機出現：

```text
Telegram 連線失敗
Telegram 訊息發送失敗
Connection timed out
Failed to resolve api.telegram.org
```

代表 Telegram API 暫時連不上。
目前 bot 已做防呆，通常不會整個崩潰，等網路恢復後可繼續使用。

---

## 3. 沒有收到自動整理

請檢查：

1. `bot.py` 是否持續執行中
2. 電腦是否在排程時間有開機
3. `.env` 是否正確
4. `bot_state.json` 是否顯示當日狀態
5. Gmail token 是否失效
6. Telegram Bot 是否能正常傳訊

---

## 4. PowerShell 出現 LF / CRLF warning

若看到：

```text
LF will be replaced by CRLF
```

這只是 Git 換行格式提醒，不是錯誤，可以忽略。

---

# 建議下一步升級方向

目前版本屬於 **V1 穩定版**，後續可升級方向：

## V2 省錢版

把自動排程改成：

* 只做規則分類 / 標籤 / 封存判斷
* 不呼叫 OpenAI API
* 只有你手動輸入「整理」時才跑 AI 摘要

這樣可以大幅降低 API 成本。

## V3 智慧分類版

增加更完整的分類，例如：

* 各家銀行分開標籤
* 登入通知 / OTP / 安全通知分開
* 訂單 / 發票 / 訂閱 / 廣告 / AI 工具 / 工作通知分類
* 自動判斷「重要待處理」與「可封存」

## V4 多平台部署

可改為部署到：

* Windows 開機自啟
* Render / Railway / VPS
* Docker 常駐服務

---

# License

This project is for personal productivity / learning use.
If you plan to deploy publicly or share with others, please review your API keys, Gmail scopes, and privacy/security settings first.
