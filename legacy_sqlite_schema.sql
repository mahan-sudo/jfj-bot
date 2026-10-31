CREATE TABLE bc_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER, src_chat INTEGER, src_mid INTEGER,
            audience TEXT, targets TEXT, idx INTEGER NOT NULL DEFAULT 0,
            ok INTEGER NOT NULL DEFAULT 0, fail INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'running',
            prog_chat INTEGER, prog_mid INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, pin INTEGER NOT NULL DEFAULT 0, fwd INTEGER NOT NULL DEFAULT 0);
CREATE TABLE discount_codes (
            code TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL DEFAULT 0,
            kind TEXT NOT NULL,
            value REAL NOT NULL,
            expires_at TEXT,
            used INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE g_chats (
            chat_id INTEGER PRIMARY KEY, title TEXT, type TEXT, seen REAL);
CREATE TABLE g_cool (user_id INTEGER PRIMARY KEY, ts REAL NOT NULL);
CREATE TABLE g_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, game TEXT, chat_id INTEGER, tid INTEGER,
            kind TEXT, stake_total REAL, payout_total REAL, detail TEXT);
CREATE TABLE g_mon (
            id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER NOT NULL, thread_id INTEGER, msg_id INTEGER,
            state TEXT NOT NULL, hp INTEGER NOT NULL, maxhp INTEGER NOT NULL, seed INTEGER NOT NULL DEFAULT 0,
            chances INTEGER NOT NULL, created REAL NOT NULL, expires REAL NOT NULL, winner INTEGER, reward REAL,
            has_photo INTEGER NOT NULL DEFAULT 0);
CREATE TABLE g_mon_hits (
            id INTEGER PRIMARY KEY AUTOINCREMENT, mon_id INTEGER NOT NULL, user_id INTEGER NOT NULL, name TEXT,
            emo TEXT, hit INTEGER NOT NULL, dmg INTEGER NOT NULL, line TEXT, ts REAL NOT NULL);
CREATE TABLE g_players (
            table_id INTEGER NOT NULL, user_id INTEGER NOT NULL, name TEXT, emo TEXT, stake REAL,
            sent INTEGER NOT NULL DEFAULT 0, sent_at REAL, value INTEGER, shown INTEGER NOT NULL DEFAULT 0,
            mult REAL, score INTEGER, payout REAL, pick TEXT, mid INTEGER,
            PRIMARY KEY (table_id, user_id));
CREATE TABLE g_stats (
            user_id INTEGER NOT NULL, game TEXT NOT NULL, wins INTEGER NOT NULL DEFAULT 0,
            losses INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (user_id, game));
CREATE TABLE g_tables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL, thread_id INTEGER, owner INTEGER NOT NULL, owner_name TEXT,
            msg_id INTEGER, state TEXT NOT NULL, stake REAL, maxp INTEGER,
            join_dl REAL, send_dl REAL, touched REAL, created REAL, game TEXT NOT NULL DEFAULT 's', mode TEXT, board TEXT, turn INTEGER, oemo TEXT);
CREATE TABLE g_xfer (
            id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER NOT NULL, thread_id INTEGER, msg_id INTEGER,
            sender INTEGER NOT NULL, sname TEXT, semo TEXT, recipient INTEGER NOT NULL, rname TEXT, remo TEXT,
            amount REAL NOT NULL, state TEXT NOT NULL, deadline REAL NOT NULL);
CREATE TABLE invoices (
            code TEXT PRIMARY KEY,
            buyer_id INTEGER NOT NULL,
            target_id INTEGER NOT NULL,
            kind TEXT NOT NULL DEFAULT 'vip',
            product_name TEXT NOT NULL,
            base_price INTEGER NOT NULL,
            final_amount INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            meta TEXT,
            chat_id INTEGER,
            message_id INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT NOT NULL, method TEXT, ref TEXT, receipt_chat INTEGER, receipt_mid INTEGER);
CREATE TABLE joins (
            user_id INTEGER NOT NULL,
            tracking_code TEXT NOT NULL,
            joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            left_at TEXT,
            PRIMARY KEY (user_id, tracking_code));
CREATE TABLE processed_updates (
            update_id INTEGER PRIMARY KEY,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE products (
            key TEXT PRIMARY KEY,
            enabled INTEGER NOT NULL DEFAULT 1,
            min_qty INTEGER NOT NULL,
            rate_cost REAL NOT NULL);
CREATE TABLE requests (
            tracking_code TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            member_count INTEGER NOT NULL,
            token_cost INTEGER NOT NULL,
            link TEXT NOT NULL,
            chat_id INTEGER,
            initial_member_count INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'in_progress',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_requested_at TEXT);
CREATE TABLE service_orders (
            tracking_code TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            service TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            extra TEXT,
            token_cost REAL NOT NULL,
            link TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, admin_notified INTEGER NOT NULL DEFAULT 0);
CREATE TABLE settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL);
CREATE TABLE sponsor_subs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            invoice_code TEXT,
            hours REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pending',
            started_at TEXT,
            ends_at TEXT,
            chat_kind TEXT,
            link_kind TEXT,
            chat_ref TEXT,
            invite_link TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE states (
            user_id INTEGER PRIMARY KEY,
            state TEXT NOT NULL,
            data TEXT);
CREATE TABLE transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            recipient_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE user_products (
            user_id INTEGER NOT NULL, key TEXT NOT NULL, PRIMARY KEY (user_id, key));
CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            first_name TEXT,
            username TEXT,
            tokens INTEGER NOT NULL DEFAULT 0,
            activity_tokens INTEGER NOT NULL DEFAULT 0,
            referral_rewarded INTEGER NOT NULL DEFAULT 0,
            vip INTEGER NOT NULL DEFAULT 0,
            referred_by INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, banned INTEGER NOT NULL DEFAULT 0, fj_ok INTEGER NOT NULL DEFAULT 0, fj_shown INTEGER NOT NULL DEFAULT 0, ref_need INTEGER, card_blocked INTEGER NOT NULL DEFAULT 0, phone TEXT, phone_req INTEGER NOT NULL DEFAULT 0);
CREATE INDEX g_log_ts ON g_log(ts);
CREATE INDEX g_mon_hits_m ON g_mon_hits(mon_id);
CREATE INDEX g_mon_state ON g_mon(state, chat_id);
CREATE INDEX g_tables_state ON g_tables(state);
CREATE INDEX g_xfer_snd ON g_xfer(sender, state);
CREATE INDEX g_xfer_st ON g_xfer(state, deadline);
