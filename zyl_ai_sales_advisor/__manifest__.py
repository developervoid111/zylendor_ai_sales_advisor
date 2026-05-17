# -*- coding: utf-8 -*-
###############################################################################
#
#    Zylentor ERP Solutions
#    Copyright (C) 2024-TODAY Zylentor ERP Solutions (<https://zylentorerp.com>)
#    Author: Zylentor ERP Solutions
#
#    PROPRIETARY LICENSE (OPL-1)
#
###############################################################################
{
    "name": "AI Sales Advisor — Intelligence & Analytics",
    "summary": (
        "AI-powered sales advisor with smart chat, seasonal analysis, "
        "top-product insights, revenue forecasting & live dashboards"
    ),
    "version": "18.0.1.1.0",
    "category": "Sales/CRM",
    "author": "Zylentor ERP Solutions",
    "support": "support@zylentorerp.com",
    "maintainer": "Zylentor ERP Solutions",
    "website": "https://zylentorerp.com",
    "license": "OPL-1",
    "price": 30.00,
    "currency": "USD",
    "sequence": 1,
    "description": """
AI Sales Advisor for Odoo 18
=============================

Turn your sales data into competitive intelligence with a built-in AI Sales Advisor.

Core Features
-------------
- **AI Sales Chat** — Ask any sales question; the AI responds exclusively as a
  professional sales advisor. Off-topic questions are gracefully rejected.
- **Top-Product Analysis** — Automatically ranks products by revenue, units sold,
  and order count across any date range.
- **Seasonal Intelligence** — Breaks down every product's performance by season
  (Spring/Summer/Autumn/Winter) with AI-generated explanations of *why* a product
  sells better at specific times.
- **Revenue Trend Charts** — Interactive monthly & quarterly revenue line/bar charts.
- **Category Breakdown** — Doughnut chart showing revenue share by product category.
- **AI-Generated Insights** — Scheduled job auto-generates actionable insights every
  week; insights are saved, searchable, and exportable.
- **KPI Cards** — Live counters for Revenue, Orders, Average Order Value, and Growth %.
- **Dashboard Explanations** — Every chart and KPI has an expandable "?" explanation
  panel written in plain business language.
- **Multi-Provider AI** — Supports OpenAI (GPT-4o, GPT-4, GPT-3.5) and
  Anthropic (Claude 3.5 Sonnet) with a simple API-key configuration.
- **Session History** — All chat sessions are saved with full message history,
  token usage, and timestamps.
""",

    # ── Dependencies ──────────────────────────────────────────────────────
    "depends": [
        "base",
        "web",
        "mail",
        "product",
        "sale_management",
        "account",
        "contacts",
    ],

    # ── Data ──────────────────────────────────────────────────────────────
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/cron_data.xml",
        "views/dashboard_view.xml",
        "views/ai_config_view.xml",
        "views/ai_chat_session_view.xml",
        "views/sales_insight_view.xml",
        "views/menus.xml",
    ],

    # ── Assets ────────────────────────────────────────────────────────────
    "assets": {
        "web.assets_backend": [
            "zyl_ai_sales_advisor/static/src/css/sales_advisor.css",
            "zyl_ai_sales_advisor/static/lib/chart.umd.min.js",
            "zyl_ai_sales_advisor/static/src/js/navbar_theme_service.js",
            "zyl_ai_sales_advisor/static/src/js/sales_advisor_dashboard.js",
            "zyl_ai_sales_advisor/static/src/xml/dashboard_template.xml",
        ],
    },

    "images": [
        "static/description/ss_01_dashboard.png",
        "static/description/ss_02_seasonal_heatmap.png",
        "static/description/ss_03_insight_detail.png",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
    "primary_color": "#1e3a5f",
    "secondary_color": "#2563EB",
}
