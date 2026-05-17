# -*- coding: utf-8 -*-
###############################################################################
#  HTTP Controller — AI chat, dashboard data, insights generation
###############################################################################
import json
import logging
import re
import urllib.request
import urllib.error
from datetime import date, timedelta

from odoo import http, _
from odoo.http import request
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
#  MARKDOWN → HTML CONVERTER
# ──────────────────────────────────────────────────────────────────────────────

def _markdown_to_html(text: str) -> str:
    """Convert a subset of Markdown to HTML suitable for Odoo's Html widget."""
    import html as html_mod
    lines = text.split("\n")
    out = []
    in_ul = False
    in_ol = False

    def close_lists():
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False

    def inline(s):
        # Escape HTML entities first
        s = html_mod.escape(s)
        # Bold+italic ***text***
        s = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", s)
        # Bold **text**
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        # Italic *text* or _text_
        s = re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)
        s = re.sub(r"_(.+?)_", r"<em>\1</em>", s)
        # Inline code `code`
        s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
        return s

    for line in lines:
        stripped = line.rstrip()

        # Headings
        m = re.match(r"^(#{1,6})\s+(.*)", stripped)
        if m:
            close_lists()
            level = min(len(m.group(1)) + 1, 6)  # h2–h6 (h1 is the title)
            out.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
            continue

        # Unordered list
        m = re.match(r"^[-*+]\s+(.*)", stripped)
        if m:
            if in_ol:
                out.append("</ol>")
                in_ol = False
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{inline(m.group(1))}</li>")
            continue

        # Ordered list
        m = re.match(r"^\d+\.\s+(.*)", stripped)
        if m:
            if in_ul:
                out.append("</ul>")
                in_ul = False
            if not in_ol:
                out.append("<ol>")
                in_ol = True
            out.append(f"<li>{inline(m.group(1))}</li>")
            continue

        # Horizontal rule
        if re.match(r"^[-*_]{3,}$", stripped):
            close_lists()
            out.append("<hr/>")
            continue

        # Blank line
        if not stripped:
            close_lists()
            out.append("")
            continue

        # Normal paragraph line
        close_lists()
        out.append(f"<p>{inline(stripped)}</p>")

    close_lists()
    # Collapse multiple blank lines
    result = "\n".join(out)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result

# ──────────────────────────────────────────────────────────────────────────────
#  SYSTEM PROMPT BUILDER
# ──────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT_TEMPLATE = """You are a professional AI Sales Advisor exclusively serving {company_name}.
Your singular purpose is to analyse sales data, surface actionable insights, and help the sales team grow revenue.

══════════════════════════════════════════
 YOUR SCOPE IS STRICTLY LIMITED TO:
══════════════════════════════════════════
✓ Sales performance analysis and KPI interpretation
✓ Product performance, cross-sell and upsell recommendations
✓ Customer behaviour patterns and segmentation
✓ Seasonal demand trends and demand forecasting
✓ Pricing strategies and revenue optimisation
✓ Promotional campaign effectiveness analysis
✓ Sales team coaching and performance guidance
✓ Inventory recommendations driven by sales data
✓ Market opportunities and competitive positioning

══════════════════════════════════════════
 YOU MUST POLITELY DECLINE OFF-TOPIC QUERIES
══════════════════════════════════════════
If the user asks about anything not related to sales, products, customers, revenue, or business growth, respond with:
"As your dedicated Sales Advisor, I'm only equipped to assist with sales-related questions. I noticed you asked about [topic] — that's outside my area of expertise. I'd love to help you with product performance, seasonal trends, or revenue growth strategies instead. What sales challenge can I tackle for you?"

══════════════════════════════════════════
 CURRENT SALES CONTEXT
══════════════════════════════════════════
Company       : {company_name}
Analysis Period: {date_from}  →  {date_to}
Currency      : {currency}
Current Season: {current_season}

📊 KEY METRICS (this period):
  Total Revenue    : {total_revenue}
  Total Orders     : {total_orders}
  Avg Order Value  : {avg_order_value}
  Revenue Growth   : {growth_pct}% vs prior period
  Unique Customers : {unique_customers}

🏆 TOP PRODUCTS BY REVENUE:
{top_products_text}

🌿 SEASONAL PERFORMANCE HIGHLIGHTS:
{seasonal_text}

📅 RECENT MONTHLY TREND:
{monthly_trend_text}

══════════════════════════════════════════
 RESPONSE GUIDELINES
══════════════════════════════════════════
1. Always cite specific numbers from the context when available.
2. Be concise but insightful — aim for 2–4 paragraphs.
3. End every response with 1–2 numbered, actionable recommendations.
4. Use professional business language with clear formatting.
5. If data is insufficient, say so and suggest what data would help.
{custom_instructions}
"""


def build_system_prompt(ctx: dict, custom_instructions: str = "") -> str:
    extra = (
        f"\n6. Additional Instructions:\n{custom_instructions}"
        if custom_instructions
        else ""
    )
    return _SYSTEM_PROMPT_TEMPLATE.format(**ctx, custom_instructions=extra)


# ──────────────────────────────────────────────────────────────────────────────
#  AI API CALLER — supports OpenAI and Anthropic
# ──────────────────────────────────────────────────────────────────────────────

def call_ai_api(config, system_prompt: str, messages: list) -> dict:
    """
    Call the configured AI provider.
    Returns: {"success": bool, "content": str, "tokens": int, "error": str}
    """
    try:
        if config.ai_provider == "openai":
            return _call_openai(config, system_prompt, messages)
        elif config.ai_provider == "anthropic":
            return _call_anthropic(config, system_prompt, messages)
        elif config.ai_provider == "google":
            return _call_google(config, system_prompt, messages)
        else:
            return {"success": False, "content": "", "tokens": 0, "error": "Unknown AI provider."}
    except Exception as exc:
        _logger.exception("AI API call failed")
        return {"success": False, "content": "", "tokens": 0, "error": str(exc)}


def _call_openai(config, system_prompt: str, messages: list) -> dict:
    payload = {
        "model": config.model_name or "gpt-4o",
        "max_tokens": config.max_tokens or 1500,
        "temperature": config.temperature if config.temperature is not None else 0.3,
        "messages": [{"role": "system", "content": system_prompt}] + messages,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
        body = json.loads(resp.read().decode("utf-8"))

    content = body["choices"][0]["message"]["content"]
    tokens = body.get("usage", {}).get("total_tokens", 0)
    return {"success": True, "content": content, "tokens": tokens, "error": ""}


def _call_anthropic(config, system_prompt: str, messages: list) -> dict:
    payload = {
        "model": config.model_name or "claude-3-5-sonnet-20241022",
        "max_tokens": config.max_tokens or 1500,
        "system": system_prompt,
        "messages": messages,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=data,
        headers={
            "Content-Type": "application/json",
            "x-api-key": config.api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
        body = json.loads(resp.read().decode("utf-8"))

    content = body["content"][0]["text"]
    usage = body.get("usage", {})
    tokens = (usage.get("input_tokens", 0) or 0) + (usage.get("output_tokens", 0) or 0)
    return {"success": True, "content": content, "tokens": tokens, "error": ""}


def _call_google(config, system_prompt: str, messages: list) -> dict:
    model = config.model_name or "gemini-2.0-flash"
    # Build contents: system instruction + conversation turns
    contents = [{"role": "user", "parts": [{"text": system_prompt}]},
                {"role": "model", "parts": [{"text": "Understood."}]}]
    for msg in messages:
        role = "model" if msg.get("role") == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": msg.get("content", "")}]})

    payload = {
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": config.max_tokens or 1500,
            "temperature": config.temperature if config.temperature is not None else 0.3,
        },
    }
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
        f":generateContent?key={config.api_key}"
    )
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
        body = json.loads(resp.read().decode("utf-8"))

    content = body["candidates"][0]["content"]["parts"][0]["text"]
    usage = body.get("usageMetadata", {})
    tokens = (usage.get("promptTokenCount", 0) or 0) + (usage.get("candidatesTokenCount", 0) or 0)
    return {"success": True, "content": content, "tokens": tokens, "error": ""}


# ──────────────────────────────────────────────────────────────────────────────
#  CONTROLLER
# ──────────────────────────────────────────────────────────────────────────────

class ZylAISalesController(http.Controller):

    # ── Internal helpers ──────────────────────────────────────────────────

    def _get_config_or_error(self):
        config = request.env["zyl.ai.config"].sudo().get_active_config()
        if not config:
            return None, {
                "success": False,
                "error": (
                    "No active AI configuration found. "
                    "Please set up your AI provider in AI Sales Advisor → Configuration."
                ),
            }
        return config, None

    def _resolve_dates(self, params):
        try:
            date_from = date.fromisoformat(params.get("date_from", ""))
        except (ValueError, TypeError):
            date_from = date.today() - timedelta(days=365)
        try:
            date_to = date.fromisoformat(params.get("date_to", ""))
        except (ValueError, TypeError):
            date_to = date.today()
        return date_from, date_to

    def _json_response(self, data, status=200):
        return request.make_response(
            json.dumps(data, default=str),
            headers=[("Content-Type", "application/json")],
            status=status,
        )

    # ── Chat endpoint ─────────────────────────────────────────────────────

    @http.route(
        "/zyl_ai_sales/api/chat",
        type="http",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def chat(self, **kwargs):
        try:
            body = json.loads(request.httprequest.data or b"{}")
        except json.JSONDecodeError:
            return self._json_response({"success": False, "error": "Invalid JSON."}, 400)

        user_message = (body.get("message") or "").strip()
        if not user_message:
            return self._json_response({"success": False, "error": "Message is required."}, 400)

        # Prevent excessively long inputs
        if len(user_message) > 2000:
            return self._json_response(
                {"success": False, "error": "Message too long (max 2000 chars)."}, 400
            )

        session_id = body.get("session_id")
        config, err = self._get_config_or_error()
        if err:
            return self._json_response(err, 503)

        # Resolve or create session
        Session = request.env["zyl.ai.chat.session"].sudo()
        if session_id:
            session = Session.browse(int(session_id))
            if not session.exists() or session.user_id.id != request.env.uid:
                return self._json_response({"success": False, "error": "Session not found."}, 404)
        else:
            snippet = user_message[:40] + ("..." if len(user_message) > 40 else "")
            session = Session.create({"name": snippet, "user_id": request.env.uid})

        # Build sales context
        date_from, date_to = self._resolve_dates(body)
        Insight = request.env["zyl.sales.insight"].sudo()
        ctx = Insight.build_sales_context_text(date_from, date_to, request.env.company.id)
        system_prompt = build_system_prompt(ctx, config.custom_instructions or "")

        # Build conversation history
        history = session.get_history_for_ai(config.max_history_messages)
        history.append({"role": "user", "content": user_message})

        # Save user message
        session.add_message("user", user_message)

        # Call AI
        result = call_ai_api(config, system_prompt, history)

        if result["success"]:
            session.add_message("assistant", result["content"], result["tokens"])
            return self._json_response(
                {
                    "success": True,
                    "reply": result["content"],
                    "session_id": session.id,
                    "tokens": result["tokens"],
                }
            )
        else:
            session.add_message("assistant", f"[Error] {result['error']}", 0)
            return self._json_response(
                {"success": False, "error": result["error"], "session_id": session.id},
                502,
            )

    # ── Dashboard data ────────────────────────────────────────────────────

    @http.route(
        "/zyl_ai_sales/api/dashboard",
        type="http",
        auth="user",
        methods=["GET"],
        csrf=False,
    )
    def dashboard(self, **kwargs):
        date_from, date_to = self._resolve_dates(kwargs)
        company_id = request.env.company.id
        Insight = request.env["zyl.sales.insight"].sudo()

        kpis = Insight.compute_kpis(date_from, date_to, company_id)
        top_products = Insight.compute_top_products(date_from, date_to, limit=10, company_id=company_id)
        monthly = Insight.compute_monthly_revenue(date_from, date_to, company_id)
        seasonal = Insight.compute_seasonal_analysis(
            date_from=date_from, date_to=date_to, top_n=10, company_id=company_id
        )
        categories = Insight.compute_category_breakdown(date_from, date_to, company_id)

        # Saved insights (last 6)
        raw_insights = (
            request.env["zyl.sales.insight"]
            .sudo()
            .search(
                [("state", "=", "published"), ("company_id", "=", company_id)],
                limit=6,
                order="create_date desc",
            )
        )
        saved_insights = [
            {
                "id": ins.id,
                "title": ins.title,
                "type": ins.insight_type,
                "summary": ins.summary or ins.content[:150],
                "priority": ins.priority,
                "period_label": ins.period_label or "",
            }
            for ins in raw_insights
        ]

        currency = request.env.company.currency_id.symbol or "$"

        return self._json_response(
            {
                "success": True,
                "currency": currency,
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(),
                "kpis": kpis,
                "top_products": top_products,
                "monthly_revenue": monthly,
                "seasonal": seasonal,
                "categories": categories,
                "saved_insights": saved_insights,
            }
        )

    # ── Generate insight on-demand ────────────────────────────────────────

    @http.route(
        "/zyl_ai_sales/api/generate_insight",
        type="http",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def generate_insight(self, **kwargs):
        if not request.env.user.has_group(
            "zyl_ai_sales_advisor.group_sales_ai_manager"
        ):
            return self._json_response({"success": False, "error": "Access denied."}, 403)

        try:
            body = json.loads(request.httprequest.data or b"{}")
        except json.JSONDecodeError:
            return self._json_response({"success": False, "error": "Invalid JSON."}, 400)

        insight_type = body.get("insight_type", "general")
        custom_prompt = (body.get("prompt") or "").strip()[:500]

        config, err = self._get_config_or_error()
        if err:
            return self._json_response(err, 503)

        date_from, date_to = self._resolve_dates(body)
        company_id = request.env.company.id
        Insight = request.env["zyl.sales.insight"].sudo()
        ctx = Insight.build_sales_context_text(date_from, date_to, company_id)
        system_prompt = build_system_prompt(ctx, config.custom_instructions or "")

        prompt_map = {
            "sales_overview": (
                "Provide a complete executive sales overview for this period. Structure your response with:"
                "\n1. **Executive Summary** — 2-3 sentence headline snapshot of overall performance."
                "\n2. **Revenue & Growth** — Total revenue, growth vs prior period, and average order value analysis."
                "\n3. **Top Products** — Which products are driving revenue, and why."
                "\n4. **Seasonal Patterns** — Key seasonal trends observed and their business implications."
                "\n5. **Customer Insights** — Order volume, unique customer count, and concentration risk."
                "\n6. **Opportunities & Risks** — 2-3 key opportunities and 1-2 risks to watch."
                "\n7. **Recommended Actions** — 3 specific, prioritised actions for the sales team this month."
                "\nBe specific with numbers from the data. Keep the tone professional but direct."
            ),
            "top_product": (
                "Analyse the top-performing products in this period. "
                "What are the key drivers of their success? Give specific recommendations."
            ),
            "seasonal": (
                "Identify the most significant seasonal patterns in the data. "
                "Explain the likely business or market reasons, and suggest how to capitalise on them."
            ),
            "recommendation": (
                "Based on all the sales data provided, give 5 specific, data-driven recommendations "
                "the sales team should implement in the next 30 days to grow revenue."
            ),
            "forecast": (
                "Based on the monthly trends and seasonal patterns, forecast the likely revenue "
                "for next month and next quarter. Explain the key assumptions."
            ),
        }
        prompt = custom_prompt or prompt_map.get(insight_type, "Provide a comprehensive sales analysis.")
        messages = [{"role": "user", "content": prompt}]

        result = call_ai_api(config, system_prompt, messages)
        if not result["success"]:
            return self._json_response({"success": False, "error": result["error"]}, 502)

        content = result["content"]
        plain_summary = re.sub(r"[*_#`]", "", content)  # strip markdown for one-liner
        html_content = _markdown_to_html(content)
        saved = Insight.create(
            {
                "title": f"Manual Insight — {insight_type.replace('_', ' ').title()}",
                "insight_type": insight_type,
                "period_label": f"{date_from.strftime('%d %b %Y')} — {date_to.strftime('%d %b %Y')}",
                "date_from": date_from,
                "date_to": date_to,
                "content": html_content,
                "summary": plain_summary[:158] + ".." if len(plain_summary) > 160 else plain_summary,
                "state": "published",
                "generated_by": "manual",
                "company_id": company_id,
            }
        )
        return self._json_response(
            {"success": True, "insight_id": saved.id, "content": content, "tokens": result["tokens"]}
        )

    # ── Feedback on chat message ──────────────────────────────────────────

    @http.route(
        "/zyl_ai_sales/api/feedback",
        type="http",
        auth="user",
        methods=["POST"],
        csrf=True,
    )
    def feedback(self, **kwargs):
        try:
            body = json.loads(request.httprequest.data or b"{}")
        except json.JSONDecodeError:
            return self._json_response({"success": False, "error": "Invalid JSON."}, 400)

        msg_id = body.get("message_id")
        rating = body.get("rating")  # "thumbs_up" | "thumbs_down"

        if not msg_id or rating not in ("thumbs_up", "thumbs_down"):
            return self._json_response({"success": False, "error": "Invalid parameters."}, 400)

        msg = request.env["zyl.ai.chat.message"].sudo().browse(int(msg_id))
        if not msg.exists():
            return self._json_response({"success": False, "error": "Message not found."}, 404)

        msg.write({"rating": rating})
        return self._json_response({"success": True})
