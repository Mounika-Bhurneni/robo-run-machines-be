# Central registry for all API-based data sources used by the AI chatbot

API_REGISTRY = {

    # ------------------------------------------------------------------
    # RISK / HEALTH / BLOCKERS
    # ------------------------------------------------------------------
    "risk_insights": {
        "url": "http://127.0.0.1:3000/analytics/risk",
        "keywords": [
            # risk & health
            "risk", "at risk issues", "blocked", "stuck", "problems",
            "health", "status", "alerts", "concerns",

            # questions
            "anything wrong", "any blockers", "what is blocked",
            "what is risky", "what needs attention",

            # incidents / PRs
            "stuck pr", "blocked pr", "long running pr",
            "delayed", "high priority issue", "critical issue"
        ]
    },

    # ------------------------------------------------------------------
    # SPRINT STATUS / PROGRESS
    # ------------------------------------------------------------------
    "sprint_insights": {
        "url": "http://127.0.0.1:3000/analytics/sprint-insights",
        "keywords": [
            "sprint", "current sprint", "iteration",
            "progress", "completion", "on track", "behind",
            "velocity", "burn down", "burnup", 
            "how is sprint going",
            "will sprint finish",
            "sprint status",
            "sprint health"
        ]
    },

    # ------------------------------------------------------------------
    # COMMITS DURING CURRENT SPRINT
    # ------------------------------------------------------------------
    "current_sprint_commits": {
        "url": "http://127.0.0.1:3000/jira/sprint/commits",
        "keywords": [
            "commit", "commits", "code", "checkins",
            "contributors", "who committed",
            "developer activity",
            "who worked this sprint",
            "commit count",
            "code contribution"
        ]
    },

    # ------------------------------------------------------------------
    # DEVELOPER WORKLOAD (WHO IS BUSY / IDLE)
    # ------------------------------------------------------------------
    "developer_workload": {
        "url": "http://127.0.0.1:3000/developers/workload",
        "keywords": [
            "workload", "busy", "overloaded", "idle",
            "who is busy", "who is free","issues",
            "developer load", "engineer load",
            "too much work",
            "not doing anything",
            "who needs help"
        ]
    },

    # ------------------------------------------------------------------
    # WORKLOAD ANALYTICS (CAPACITY / REDISTRIBUTION)
    # ------------------------------------------------------------------
    "workload_analytics": {
        "url": "http://127.0.0.1:3000/analytics/workload",
        "keywords": [
            "capacity", "utilization", "load balance",
            "redistribute", "reassign",
            "over capacity", "under capacity",
            "team capacity",
            "resource planning",
            "who can take more work"
        ]
    },

    # ------------------------------------------------------------------
    # TEAM INSIGHTS / PERFORMANCE
    # ------------------------------------------------------------------
    "team_insights": {
        "url": "http://127.0.0.1:3000/jira/team/insights",
        "keywords": [
            "team", "team performance", "productivity",
            "team health", "team output","issues","sprint health",
            "who is performing",
            "top performers",
            "team metrics", "how is team performing", "most productive", "tasks"
        ]
    },

    # ------------------------------------------------------------------
    # TASKS FOR TODAY (WHO + WHAT)
    # ------------------------------------------------------------------
    "tasks_today": {
        "url": "http://127.0.0.1:3000/jira/tasks/today",
        "keywords": [
            "today", "today tasks",
            "what should i do today",
            "my tasks",
            "assigned today",
            "work for today",
            "daily tasks",
            "who is working today",
            "assigned to whom", "tasks", "tasks assigned"
        ]
    },

    # ------------------------------------------------------------------
    # RECENT ACTIVITY (TIMELINE VIEW)
    # ------------------------------------------------------------------
    "recent_activity": {
        "url": "http://127.0.0.1:3000/activity/recent",
        "keywords": [
            "recent", "latest", "activity",
            "what changed",
            "what happened",
            "recent updates",
            "recent events",
            "timeline",
            "history", "recently", "yesterday", "changed"
        ]
    },

    # ------------------------------------------------------------------
    # GIT ACTIVITY (COMMITS + PRs)
    # ------------------------------------------------------------------
    "recent_git_activity": {
        "url": "http://127.0.0.1:3000/git/recent",
        "keywords": [
            "git", "github",
            "commits", "prs", "pull request",
            "recent commits",
            "recent prs", "recent pull request",
            "code changes",
            "who committed",
            "who opened pr", "pending pr"
        ]
    },

    # ------------------------------------------------------------------
    # WEEKLY ANALYTICS
    # ------------------------------------------------------------------
    "weekly_analytics": {
        "url": "http://127.0.0.1:3000/analytics/weekly",
        "keywords": [
            "week", "weekly",
            "last week",
            "weekly summary",
            "weekly report",
            "weekly performance",
            "last 7 days", 
            "what happened this week"
        ]
    },

    # ------------------------------------------------------------------
    # PR BOTTLENECKS (WHO IS STUCK)
    # ------------------------------------------------------------------
    "pr_bottleneck": {
        "url": "http://127.0.0.1:3000/prs/bottlenecks",
        "keywords": [
            "pr", "pull request",
            "stuck pr", "blocked pr",
            "long running pr",
            "waiting for review",
            "who is stuck",
            "who has stuck prs",
            "who owns these prs",
            "Which PRs need attention?"
        ]
    }
}
