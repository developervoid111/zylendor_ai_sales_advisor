# -*- coding: utf-8 -*-
###############################################################################
#  Sales Insight — AI-generated insight records + all data-computation helpers
###############################################################################
import json
import logging
from datetime import date, datetime, timedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Season mapping  month -> (season_key, season_label)
SEASON_MAP = {
    1: ("winter", "Winter"),
    2: ("winter", "Winter"),
    3: ("spring", "Spring"),
    4: ("spring", "Spring"),
    5: ("spring", "Spring"),
    6: ("summer", "Summer"),
    7: ("summer", "Summer"),
    8: ("summer", "Summer"),
    9: ("autumn", "Autumn"),
    10: ("autumn", "Autumn"),
    11: ("autumn", "Autumn"),
    12: ("winter", "Winter"),
}

SEASON_MONTHS = {
    "spring": [3, 4, 5],
    "summer": [6, 7, 8],
    "autumn": [9, 10, 11],
    "winter": [12, 1, 2],
}

SEASON_ICONS = {
    "spring": "🌸",
    "summer": "☀️",
    "autumn": "🍂",
    "winter": "❄️",
}


class ZylSalesInsight(models.Model):
    _name = "zyl.sales.insight"
    _description = "AI-Generated Sales Insight"
    _rec_name = "title"
    _order = "create_date desc"

    title = fields.Char("Insight Title", required=True)
    insight_type = fields.Selection(
        [
            ("sales_overview", "Sales Overview"),
            ("top_product", "Top Product"),
            ("seasonal", "Seasonal Trend"),
            ("revenue_trend", "Revenue Trend"),
            ("category", "Category Analysis"),
            ("growth", "Growth / Decline"),
            ("recommendation", "Recommendation"),
            ("forecast", "Forecast"),
            ("general", "General"),
        ],
        string="Type",
        required=True,
        default="general",
    )
    period_label = fields.Char("Period", help="E.g. 'Q2 2025' or 'Last 12 months'")
    date_from = fields.Date("From")
    date_to = fields.Date("To")
    content = fields.Html("AI Insight", required=True, sanitize=False)
    summary = fields.Char("Summary (one-liner)", size=160)
    raw_data = fields.Text("Raw Data (JSON)", help="The underlying sales data used.")
    state = fields.Selection(
        [("draft", "Draft"), ("published", "Published"), ("archived", "Archived")],
        default="published",
    )
    priority = fields.Selection(
        [("0", "Normal"), ("1", "Important"), ("2", "Critical")],
        default="0",
        string="Priority",
    )
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company
    )
    generated_by = fields.Selection(
        [("auto", "Auto (Cron)"), ("manual", "Manual")], default="manual"
    )

    # ══════════════════════════════════════════════════════════════════════
    #  DATA COMPUTATION HELPERS — used by the controller & cron jobs
    # ══════════════════════════════════════════════════════════════════════

    @api.model
    def compute_top_products(self, date_from, date_to, limit=10, company_id=None):
        """Return top products ranked by revenue in the given period."""
        params = [date_from, date_to]
        company_filter = ""
        if company_id:
            company_filter = "AND so.company_id = %s"
            params.append(company_id)

        query = """
            SELECT
                pp.id                               AS product_id,
                COALESCE(pt.name->>'en_US', '')     AS product_name,
                COALESCE(pc.name, '')               AS category_name,
                SUM(sol.price_subtotal)             AS revenue,
                SUM(sol.product_uom_qty)            AS qty_sold,
                COUNT(DISTINCT so.id)               AS order_count,
                AVG(sol.price_unit)                 AS avg_price
            FROM sale_order_line sol
            JOIN sale_order      so  ON so.id  = sol.order_id
            JOIN product_product pp  ON pp.id  = sol.product_id
            JOIN product_template pt ON pt.id  = pp.product_tmpl_id
            LEFT JOIN product_category pc ON pc.id = pt.categ_id
            WHERE so.state IN ('sale','done')
              AND so.date_order::date BETWEEN %s AND %s
              {company_filter}
            GROUP BY pp.id, pt.name, pc.name
            ORDER BY revenue DESC
            LIMIT %s
        """.format(
            company_filter=company_filter
        )
        params.append(limit)
        self.env.cr.execute(query, params)
        rows = self.env.cr.dictfetchall()

        # Add rank
        for i, row in enumerate(rows, 1):
            row["rank"] = i
            row["revenue"] = float(row["revenue"] or 0)
            row["qty_sold"] = float(row["qty_sold"] or 0)
            row["avg_price"] = float(row["avg_price"] or 0)
        return rows

    @api.model
    def compute_seasonal_analysis(self, date_from=None, date_to=None, year=None, top_n=10, company_id=None):
        """
        Return per-product sales broken down by season across the full date range.
        Result shape:
          {
            "seasons": ["Spring","Summer","Autumn","Winter"],
            "products": [
              {
                "product_name": "...",
                "data": {"Spring": 1200.0, "Summer": 3400.0, ...},
                "best_season": "Summer",
                "worst_season": "Spring"
              }, ...
            ]
          }
        """
        if date_from is None:
            date_from = (date.today().replace(month=1, day=1) - timedelta(days=365))
        if date_to is None:
            date_to = date.today()

        params = [date_from, date_to]
        company_filter = ""
        if company_id:
            company_filter = "AND so.company_id = %s"
            params.append(company_id)

        query = """
            SELECT
                COALESCE(pt.name->>'en_US', 'Unknown') AS product_name,
                EXTRACT(MONTH FROM so.date_order)::int AS month,
                SUM(sol.price_subtotal) AS revenue,
                SUM(sol.product_uom_qty) AS qty_sold
            FROM sale_order_line sol
            JOIN sale_order      so  ON so.id  = sol.order_id
            JOIN product_product pp  ON pp.id  = sol.product_id
            JOIN product_template pt ON pt.id  = pp.product_tmpl_id
            WHERE so.state IN ('sale','done')
              AND so.date_order::date BETWEEN %s AND %s
              {company_filter}
            GROUP BY pt.name, month
            ORDER BY SUM(sol.price_subtotal) DESC
        """.format(
            company_filter=company_filter
        )
        self.env.cr.execute(query, params)
        rows = self.env.cr.dictfetchall()

        # Aggregate by product and season
        product_map = {}
        for row in rows:
            pname = row["product_name"]
            month = int(row["month"])
            season_key, season_label = SEASON_MAP.get(month, ("winter", "Winter"))
            rev = float(row["revenue"] or 0)

            if pname not in product_map:
                product_map[pname] = {
                    "product_name": pname,
                    "total_revenue": 0.0,
                    "data": {"Spring": 0.0, "Summer": 0.0, "Autumn": 0.0, "Winter": 0.0},
                }
            product_map[pname]["data"][season_label] += rev
            product_map[pname]["total_revenue"] += rev

        # Sort by total revenue, take top N
        sorted_products = sorted(
            product_map.values(), key=lambda x: x["total_revenue"], reverse=True
        )[:top_n]

        seasons = ["Spring", "Summer", "Autumn", "Winter"]
        for prod in sorted_products:
            season_data = prod["data"]
            non_zero = {s: v for s, v in season_data.items() if v > 0}
            if non_zero:
                prod["best_season"] = max(non_zero, key=non_zero.get)
                prod["worst_season"] = min(non_zero, key=non_zero.get)
            else:
                prod["best_season"] = None
                prod["worst_season"] = None

        return {"seasons": seasons, "products": sorted_products}

    @api.model
    def compute_monthly_revenue(self, date_from, date_to, company_id=None):
        """Return monthly revenue totals for the given date range."""
        params = [date_from, date_to]
        company_filter = ""
        if company_id:
            company_filter = "AND so.company_id = %s"
            params.append(company_id)

        query = """
            SELECT
                TO_CHAR(so.date_order, 'YYYY-MM') AS month,
                SUM(sol.price_subtotal)            AS revenue,
                COUNT(DISTINCT so.id)              AS orders
            FROM sale_order_line sol
            JOIN sale_order so ON so.id = sol.order_id
            WHERE so.state IN ('sale','done')
              AND so.date_order::date BETWEEN %s AND %s
              {company_filter}
            GROUP BY month
            ORDER BY month
        """.format(
            company_filter=company_filter
        )
        self.env.cr.execute(query, params)
        rows = self.env.cr.dictfetchall()
        for row in rows:
            row["revenue"] = float(row["revenue"] or 0)
        return rows

    @api.model
    def compute_kpis(self, date_from, date_to, company_id=None):
        """Compute headline KPIs for the given date range."""
        params = [date_from, date_to]
        company_filter = ""
        if company_id:
            company_filter = "AND so.company_id = %s"
            params.append(company_id)

        query = """
            SELECT
                SUM(so.amount_untaxed)       AS total_revenue,
                COUNT(DISTINCT so.id)        AS total_orders,
                AVG(so.amount_untaxed)       AS avg_order_value,
                COUNT(DISTINCT so.partner_id) AS unique_customers
            FROM sale_order so
            WHERE so.state IN ('sale','done')
              AND so.date_order::date BETWEEN %s AND %s
              {company_filter}
        """.format(
            company_filter=company_filter
        )
        self.env.cr.execute(query, params)
        row = self.env.cr.dictfetchone() or {}

        # Previous period for growth calculation
        period_days = (date_to - date_from).days + 1
        prev_to = date_from - timedelta(days=1)
        prev_from = prev_to - timedelta(days=period_days - 1)

        params_prev = [prev_from, prev_to]
        if company_id:
            params_prev.append(company_id)
        self.env.cr.execute(
            """
            SELECT SUM(so.amount_untaxed) AS prev_revenue
            FROM sale_order so
            WHERE so.state IN ('sale','done')
              AND so.date_order::date BETWEEN %s AND %s
              {company_filter}
        """.format(
                company_filter=company_filter
            ),
            params_prev,
        )
        prev = self.env.cr.dictfetchone() or {}

        current_rev = float(row.get("total_revenue") or 0)
        prev_rev = float(prev.get("prev_revenue") or 0)
        growth_pct = (
            round(((current_rev - prev_rev) / prev_rev) * 100, 2)
            if prev_rev > 0
            else 0.0
        )

        return {
            "total_revenue": current_rev,
            "total_orders": int(row.get("total_orders") or 0),
            "avg_order_value": float(row.get("avg_order_value") or 0),
            "unique_customers": int(row.get("unique_customers") or 0),
            "growth_pct": growth_pct,
            "prev_revenue": prev_rev,
        }

    @api.model
    def compute_category_breakdown(self, date_from, date_to, company_id=None):
        """Revenue breakdown by product category."""
        params = [date_from, date_to]
        company_filter = ""
        if company_id:
            company_filter = "AND so.company_id = %s"
            params.append(company_id)

        query = """
            SELECT
                COALESCE(pc.name, 'Uncategorised')            AS category_name,
                SUM(sol.price_subtotal)                        AS revenue,
                COUNT(DISTINCT sol.product_id)                 AS product_count
            FROM sale_order_line sol
            JOIN sale_order      so  ON so.id  = sol.order_id
            JOIN product_product pp  ON pp.id  = sol.product_id
            JOIN product_template pt ON pt.id  = pp.product_tmpl_id
            LEFT JOIN product_category pc ON pc.id = pt.categ_id
            WHERE so.state IN ('sale','done')
              AND so.date_order::date BETWEEN %s AND %s
              {company_filter}
            GROUP BY pc.name
            ORDER BY revenue DESC
            LIMIT 8
        """.format(
            company_filter=company_filter
        )
        self.env.cr.execute(query, params)
        rows = self.env.cr.dictfetchall()
        for row in rows:
            row["revenue"] = float(row["revenue"] or 0)
        return rows

    @api.model
    def build_sales_context_text(self, date_from, date_to, company_id=None):
        """
        Build a human-readable sales context string injected into the AI system prompt.
        """
        company = self.env["res.company"].browse(company_id) if company_id else self.env.company
        currency = company.currency_id.symbol or "$"

        kpis = self.compute_kpis(date_from, date_to, company_id)
        top_products = self.compute_top_products(date_from, date_to, limit=10, company_id=company_id)
        monthly = self.compute_monthly_revenue(date_from, date_to, company_id)
        seasonal = self.compute_seasonal_analysis(
            date_from=date_from, date_to=date_to, top_n=5, company_id=company_id
        )

        # Seasonal summary text
        seasonal_lines = []
        for prod in seasonal.get("products", [])[:5]:
            best = prod.get("best_season", "N/A")
            data = prod.get("data", {})
            top_rev = max(data.values()) if data else 0
            seasonal_lines.append(
                f"  • {prod['product_name']}: Best in {best} ({currency}{top_rev:,.0f})"
            )
        seasonal_text = "\n".join(seasonal_lines) or "  No seasonal data available."

        # Top products text
        top_product_lines = []
        for p in top_products[:10]:
            top_product_lines.append(
                f"  {p['rank']}. {p['product_name']} — "
                f"{currency}{p['revenue']:,.2f} revenue, "
                f"{p['qty_sold']:.0f} units"
            )
        top_products_text = "\n".join(top_product_lines) or "  No product data."

        # Monthly trend (last 3 months)
        monthly_lines = []
        for m in monthly[-3:]:
            monthly_lines.append(
                f"  {m['month']}: {currency}{m['revenue']:,.2f} ({m['orders']} orders)"
            )
        monthly_trend_text = "\n".join(monthly_lines) or "  No monthly data."

        # Current season
        today_month = date.today().month
        _, current_season = SEASON_MAP.get(today_month, ("winter", "Winter"))

        return {
            "company_name": company.name,
            "currency": currency,
            "date_from": date_from.strftime("%d %b %Y"),
            "date_to": date_to.strftime("%d %b %Y"),
            "total_revenue": f"{currency}{kpis['total_revenue']:,.2f}",
            "total_orders": str(kpis["total_orders"]),
            "avg_order_value": f"{currency}{kpis['avg_order_value']:,.2f}",
            "growth_pct": f"{kpis['growth_pct']:+.1f}",
            "unique_customers": str(kpis["unique_customers"]),
            "top_products_text": top_products_text,
            "seasonal_text": seasonal_text,
            "monthly_trend_text": monthly_trend_text,
            "current_season": current_season,
        }

    # ── Cron: Auto-generate insights ──────────────────────────────────────
    @api.model
    def cron_generate_weekly_insights(self):
        """Called weekly by the scheduler to auto-generate and save insights."""
        configs = self.env["zyl.ai.config"].search(
            [("active", "=", True), ("auto_insights_enabled", "=", True)]
        )
        for config in configs:
            try:
                self._generate_and_save_insights(config)
            except Exception as exc:
                _logger.error("AI insight generation failed: %s", exc)

    def _generate_and_save_insights(self, config):
        """Generate AI insights using the active config and save them."""
        from odoo.addons.zyl_ai_sales_advisor.controllers.main import (
            call_ai_api,
            build_system_prompt,
        )

        today = date.today()
        date_from = today - timedelta(days=config.analysis_days)
        ctx = self.build_sales_context_text(date_from, today, config.company_id.id)

        prompts = [
            (
                "top_product",
                "Summarise the top 3 performing products this period and explain "
                "why they are likely performing well based on the data provided.",
            ),
            (
                "seasonal",
                "Identify the strongest seasonal pattern in the sales data and "
                "explain the likely business reasons behind it.",
            ),
            (
                "recommendation",
                "Based on the sales data, give 3 specific, actionable recommendations "
                "the sales team should implement in the next 30 days.",
            ),
        ]

        for insight_type, prompt in prompts:
            system_prompt = build_system_prompt(ctx, config.custom_instructions)
            messages = [{"role": "user", "content": prompt}]
            result = call_ai_api(config, system_prompt, messages)

            if result.get("success"):
                self.create(
                    {
                        "title": f"Auto Insight — {insight_type.replace('_', ' ').title()} ({today.strftime('%b %Y')})",
                        "insight_type": insight_type,
                        "period_label": f"{date_from.strftime('%d %b %Y')} — {today.strftime('%d %b %Y')}",
                        "date_from": date_from,
                        "date_to": today,
                        "content": result["content"],
                        "summary": result["content"][:158] + ".." if len(result["content"]) > 160 else result["content"],
                        "state": "published",
                        "generated_by": "auto",
                        "company_id": config.company_id.id,
                    }
                )

    # ══════════════════════════════════════════════════════════════════════
    #  STATE ACTIONS
    # ══════════════════════════════════════════════════════════════════════

    def action_publish(self):
        self.write({"state": "published"})

    def action_archive(self):
        self.write({"state": "archived"})
