CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,                 -- telegram_id
    openai_api_key_encrypted BLOB,
    language TEXT,                          -- ru | en | he, NULL = not chosen yet
    created_at TEXT NOT NULL,
    last_seen_at TEXT
);

CREATE TABLE IF NOT EXISTS profiles (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    weight REAL,
    height REAL,
    age INTEGER,
    gender TEXT,
    activity_level TEXT,
    goal TEXT,
    deficit_percent INTEGER,
    target_kcal INTEGER,
    target_protein INTEGER,
    target_fat INTEGER,
    target_carbs INTEGER,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS food_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date TEXT NOT NULL,
    meal_type TEXT NOT NULL DEFAULT 'unspecified',
    item_name TEXT NOT NULL,
    grams REAL,
    kcal REAL NOT NULL,
    protein REAL NOT NULL,
    fat REAL NOT NULL,
    carbs REAL NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_food_log_user_date ON food_log(user_id, date);

CREATE TABLE IF NOT EXISTS weight_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date TEXT NOT NULL,
    weight REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_weight_log_user_date ON weight_log(user_id, date);

CREATE TABLE IF NOT EXISTS weight_checkin_status (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    week_start_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',   -- pending | skipped | done
    last_reminder_at TEXT,
    PRIMARY KEY (user_id, week_start_date)
);

CREATE TABLE IF NOT EXISTS known_foods (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name_normalized TEXT NOT NULL,
    display_name TEXT NOT NULL,
    kcal_per_100g REAL NOT NULL,
    protein_per_100g REAL NOT NULL,
    fat_per_100g REAL NOT NULL,
    carbs_per_100g REAL NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, name_normalized)
);
