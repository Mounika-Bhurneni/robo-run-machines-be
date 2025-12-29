# Fallback DB queries when APIs do not fully answer user questions

DB_QUERY_REGISTRY = {

    # ==================================================
    # JIRA ISSUES
    # ==================================================
    "jira_issue_status_summary": {
        "keywords": [
            "jira", "issue", "issues",
            "status", "open", "closed",
            "in progress", "done",
            "assigned to", "assignee",
            "who owns", "owner",
            "list issues", "show issues"
        ],
        "sql": """
            SELECT status, COUNT(*) AS count
            FROM jira_issues
            GROUP BY status
            ORDER BY count DESC
        """
    },

    "jira_priority_breakdown": {
        "keywords": [
            "priority", "severity",
            "high", "critical", "important",
            "urgent issues"
        ],
        "sql": """
            SELECT priority, COUNT(*) AS count
            FROM jira_issues
            GROUP BY priority
            ORDER BY count DESC
        """
    },

    "stale_jira_issues": {
        "keywords": [
            "stale", "inactive",
            "old issues", "ignored issues",
            "not updated", "pending long",
            "issues not touched"
        ],
        "sql": """
            SELECT issue_key, assignee_name, status, updated_at
            FROM jira_issues
            WHERE updated_at < NOW() - INTERVAL '7 days'
            ORDER BY updated_at ASC
            LIMIT 10
        """
    },

    # ==================================================
    # USERS / TEAM
    # ==================================================
    "active_users": {
        "keywords": [
            "users", "team", "members",
            "developers", "engineers",
            "who is on the team",
            "who is working"
        ],
        "sql": """
            SELECT display_name, email, roles, created_at
            FROM users
            ORDER BY created_at DESC
            LIMIT 20
        """
    },

    "user_roles_breakdown": {
        "keywords": [
            "roles", "user roles",
            "who is manager",
            "who is dev",
            "team roles"
        ],
        "sql": """
            SELECT roles, COUNT(*) AS count
            FROM users
            GROUP BY roles
        """
    },

    # ==================================================
    # GIT / COMMITS
    # ==================================================
    "recent_commits": {
        "keywords": [
            "recent commits",
            "latest commits",
            "code changes",
            "github commits",
            "who committed",
            "who pushed code"
        ],
        "sql": """
            SELECT repo, author_email, message, timestamp
            FROM git_commits
            ORDER BY timestamp DESC
            LIMIT 10
        """
    },

    "top_committers": {
        "keywords": [
            "top committers",
            "most commits",
            "active developers",
            "who commits most"
        ],
        "sql": """
            SELECT author_email, COUNT(*) AS commits
            FROM git_commits
            GROUP BY author_email
            ORDER BY commits DESC
            LIMIT 10
        """
    },

    # ==================================================
    # PULL REQUESTS
    # ==================================================
    "open_pull_requests": {
        "keywords": [
            "open pr",
            "open pull requests",
            "pending prs",
            "prs not merged",
            "who has open prs"
        ],
        "sql": """
            SELECT pr_number, title, author_login, state, timestamp
            FROM pull_requests
            WHERE state = 'open'
            ORDER BY timestamp DESC
            LIMIT 10
        """
    },

    "stale_pull_requests": {
        "keywords": [
            "stale pr",
            "stuck pr",
            "blocked pr",
            "long running pr",
            "pending review",
            "who is stuck",
            "waiting on who"
        ],
        "sql": """
            SELECT pr_number, title, author_login, state, timestamp
            FROM pull_requests
            WHERE timestamp < NOW() - INTERVAL '3 days'
            ORDER BY timestamp ASC
            LIMIT 10
        """
    },

    # ==================================================
    # INCIDENTS / ALERTS
    # ==================================================
    "open_incidents": {
        "keywords": [
            "incidents",
            "alerts",
            "outages",
            "problems",
            "service down",
            "production issue"
        ],
        "sql": """
            SELECT incident_number, severity, state, assigned_user_id, updated_at
            FROM servicenow_incidents
            WHERE state NOT IN ('Resolved', 'Closed')
            ORDER BY updated_at DESC
            LIMIT 10
        """
    },

    # ==================================================
    # ACTIVITY / TIMELINE
    # ==================================================
    "recent_activity_events": {
        "keywords": [
            "activity",
            "timeline",
            "recent events",
            "what happened",
            "history",
            "audit",
            "event log",
            "changes"
        ],
        "sql": """
            SELECT type, source_ref, occurred_at
            FROM activity_events
            ORDER BY occurred_at DESC
            LIMIT 20
        """
    }
}
