DB_QUERY_REGISTRY = {

    # ==================================================
    # JIRA — TEAM LEVEL BREAKDOWNS
    # ==================================================
    "jira_status_breakdown": """
        SELECT status, COUNT(*) AS count
        FROM jira_issues
        GROUP BY status
    """,

    "jira_priority_breakdown": """
        SELECT priority, COUNT(*) AS count
        FROM jira_issues
        GROUP BY priority
    """,

    "jira_assignee_status_breakdown": """
        SELECT assignee_name, status, COUNT(*) AS count
        FROM jira_issues
        WHERE assignee_name IS NOT NULL
        GROUP BY assignee_name, status
        ORDER BY count DESC
        LIMIT 100
    """,

    "jira_assignee_priority_breakdown": """
        SELECT assignee_name, priority, COUNT(*) AS count
        FROM jira_issues
        WHERE assignee_name IS NOT NULL
        GROUP BY assignee_name, priority
        ORDER BY count DESC
        LIMIT 100
    """,

    # ==================================================
    # JIRA — STALE / RISK / NOTABLE ISSUES
    # ==================================================
    "stale_jira_issues": """
        SELECT issue_key, assignee_name, priority, status, updated_at
        FROM jira_issues
        WHERE updated_at < NOW() - INTERVAL '7 days'
        ORDER BY updated_at ASC
        LIMIT 20
    """,

    "high_priority_open_jira": """
        SELECT issue_key, assignee_name, status, updated_at
        FROM jira_issues
        WHERE priority = 'High'
          AND status NOT IN ('Done', 'Closed')
        ORDER BY updated_at ASC
        LIMIT 20
    """,

    # ==================================================
    # SPRINT — METADATA
    # ==================================================
    "latest_active_sprint": """
        SELECT name, start_date, end_date, state
        FROM jira_sprints
        WHERE state = 'active'
        ORDER BY start_date DESC
        LIMIT 1
    """,

    "recent_sprints": """
        SELECT name, start_date, end_date, state
        FROM jira_sprints
        ORDER BY start_date DESC
        LIMIT 3
    """,

    # ==================================================
    # SPRINT — PROGRESS & COMPLETION
    # ==================================================
    "sprint_issue_progress": """
        SELECT
            s.name AS sprint_name,
            i.status,
            COUNT(*) AS count
        FROM jira_issues i
        JOIN jira_sprints s ON i.sprint_id = s.id
        WHERE s.state = 'active'
        GROUP BY s.name, i.status
    """,

    "sprint_completion_ratio": """
        SELECT
            s.name AS sprint_name,
            SUM(CASE WHEN i.status IN ('Done', 'Closed') THEN 1 ELSE 0 END) AS completed,
            COUNT(*) AS total
        FROM jira_issues i
        JOIN jira_sprints s ON i.sprint_id = s.id
        WHERE s.state = 'active'
        GROUP BY s.name
    """,

    # ==================================================
    # SPRINT — VELOCITY (CURRENT vs PREVIOUS)
    # ==================================================
    "sprint_velocity_comparison": """
        SELECT
            s.name AS sprint_name,
            COUNT(*) FILTER (WHERE i.status IN ('Done', 'Closed')) AS completed_issues
        FROM jira_issues i
        JOIN jira_sprints s ON i.sprint_id = s.id
        GROUP BY s.name
        ORDER BY s.start_date DESC
        LIMIT 2
    """,

    # ==================================================
    # GIT — PRs & COMMITS
    # ==================================================
    "open_prs_by_author": """
        SELECT author_login, COUNT(*) AS open_prs
        FROM pull_requests
        WHERE state = 'open'
        GROUP BY author_login
        ORDER BY open_prs DESC
    """,

    "stale_prs": """
        SELECT pr_number, author_login, state, timestamp
        FROM pull_requests
        WHERE state = 'open'
          AND timestamp < NOW() - INTERVAL '2 days'
        ORDER BY timestamp ASC
        LIMIT 20
    """,

    "recent_commits_by_author": """
        SELECT author_email, COUNT(*) AS commit_count
        FROM git_commits
        GROUP BY author_email
        ORDER BY commit_count DESC
        LIMIT 20
    """,

    # ==================================================
    # USERS
    # ==================================================
    "users": """
        SELECT id, display_name, email, roles
        FROM users
        LIMIT 100
    """
}
