

# ======================
# API BEHAVIOR
# ======================

MAX_SOURCES = 5                 # Max APIs + DB queries per question
API_TIMEOUT = 40                # Seconds
MAX_DB_ROWS = 100               # Safety cap

# ======================
# OPENAI
# ======================

OPENAI_MODEL = "gpt-4o-mini"
OPENAI_TEMPERATURE = 0          # FACTS → deterministic
OPENAI_MAX_TOKENS = 800

# ======================
# EXECUTION SAFETY
# ======================

ALLOW_PARALLEL_CALLS = False    # Keep false for now
FAIL_SILENTLY = True            # Ignore failing sources

# ======================
# RESPONSE LIMITS
# ======================

MAX_FACT_LINES = 200            # Prevent runaway outputs
