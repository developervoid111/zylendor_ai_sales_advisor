# -*- coding: utf-8 -*-
###############################################################################
#  AI Configuration — stores API keys, model choice, and prompt settings
###############################################################################
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ZylAIConfig(models.Model):
    _name = "zyl.ai.config"
    _description = "AI Sales Advisor Configuration"
    _rec_name = "name"

    name = fields.Char("Configuration Name", required=True, default="Default AI Config")
    active = fields.Boolean("Active", default=True)
    company_id = fields.Many2one(
        "res.company", "Company", required=True, default=lambda self: self.env.company
    )

    # ── AI Provider ───────────────────────────────────────────────────────
    ai_provider = fields.Selection(
        [
            ("openai", "OpenAI"),
            ("anthropic", "Anthropic"),
            ("google", "Google Gemini"),
        ],
        string="AI Provider",
        required=True,
        default="openai",
    )
    api_key = fields.Char(
        "API Key",
        required=True,
        help="Your AI provider API key. Visible only to Administrators.",
    )

    # ── Model selection per provider ──────────────────────────────────────
    openai_model = fields.Selection(
        [
            # ── Latest / Flagship ──────────────────────────────────────
            ("gpt-4.5-preview",   "GPT-4.5 Preview  (Feb 2026 · paid)"),
            ("gpt-4.1",           "GPT-4.1  (Apr 2026 · paid)"),
            ("gpt-4.1-mini",      "GPT-4.1 Mini  (fast · paid)"),
            ("gpt-4.1-nano",      "GPT-4.1 Nano  (lightest · paid)"),
            # ── GPT-4o family ─────────────────────────────────────────
            ("gpt-4o",            "GPT-4o  (multimodal · paid)"),
            ("gpt-4o-mini",       "GPT-4o Mini  (budget · paid)"),
            # ── Reasoning / o-series ──────────────────────────────────
            ("o4-mini",           "o4-mini  (reasoning · paid)"),
            ("o3",                "o3  (reasoning, most powerful · paid)"),
            ("o3-mini",           "o3-mini  (reasoning · paid)"),
            ("o1",                "o1  (reasoning · paid)"),
            ("o1-mini",           "o1-mini  (reasoning budget · paid)"),
            ("o1-pro",            "o1 Pro  (pro subscription)"),
            # ── Custom ────────────────────────────────────────────────
            ("custom",            "Custom…  (type any model ID)"),
        ],
        string="OpenAI Model",
        default="gpt-4.1-mini",
    )
    anthropic_model = fields.Selection(
        [
            # ── Claude 3.7 ────────────────────────────────────────────
            ("claude-3-7-sonnet-20250219",  "Claude 3.7 Sonnet  (extended thinking · paid)"),
            # ── Claude 3.5 ────────────────────────────────────────────
            ("claude-3-5-sonnet-20241022",  "Claude 3.5 Sonnet  (smart · paid)"),
            ("claude-3-5-haiku-20241022",   "Claude 3.5 Haiku  (fast & cheap · paid)"),
            # ── Claude 3 ──────────────────────────────────────────────
            ("claude-3-opus-20240229",      "Claude 3 Opus  (powerful · paid)"),
            ("claude-3-sonnet-20240229",    "Claude 3 Sonnet  (paid)"),
            ("claude-3-haiku-20240307",     "Claude 3 Haiku  (budget · paid)"),
            # ── Custom ────────────────────────────────────────────────
            ("custom",                      "Custom…  (type any model ID)"),
        ],
        string="Anthropic Model",
        default="claude-3-5-haiku-20241022",
    )
    google_model = fields.Selection(
        [
            # ── Gemini 3.x (experimental) ────────────────────────────
            ("gemini-3.1-pro-preview",          "Gemini 3.1 Pro Preview  (experimental · latest)"),
            ("gemini-3.1-flash-lite",           "Gemini 3.1 Flash Lite  (experimental · fast)"),
            ("gemini-3-pro-preview",            "Gemini 3 Pro Preview  (experimental)"),
            ("gemini-3-flash-preview",          "Gemini 3 Flash Preview  (experimental)"),
            # ── Gemini 2.5 ───────────────────────────────────────────
            ("gemini-2.5-pro",                  "Gemini 2.5 Pro  (most capable · free tier)"),
            ("gemini-2.5-flash",                "Gemini 2.5 Flash  (fast & capable · free tier)"),
            ("gemini-2.5-flash-lite",           "Gemini 2.5 Flash Lite  (lightweight · free tier)"),
            # ── Gemini 2.0 ───────────────────────────────────────────
            ("gemini-2.0-flash",                "Gemini 2.0 Flash  (stable · free tier)"),
            ("gemini-2.0-flash-lite",           "Gemini 2.0 Flash Lite  (lightest · free tier)"),
            # ── Custom ───────────────────────────────────────────────
            ("custom",                          "Custom…  (type any model ID)"),
        ],
        string="Google Model",
        default="gemini-2.5-flash",
    )
    custom_model_name = fields.Char(
        "Custom Model ID",
        help="Enter the exact model ID when 'Custom…' is selected above.",
    )

    # Resolved model name sent to the API (computed from the selections above)
    model_name = fields.Char(
        "Model Name",
        compute="_compute_model_name",
        store=True,
        readonly=True,
    )

    @api.depends("ai_provider", "openai_model", "anthropic_model", "google_model", "custom_model_name")
    def _compute_model_name(self):
        for rec in self:
            if rec.ai_provider == "openai":
                rec.model_name = rec.custom_model_name if rec.openai_model == "custom" else (rec.openai_model or "gpt-4.1-mini")
            elif rec.ai_provider == "anthropic":
                rec.model_name = rec.custom_model_name if rec.anthropic_model == "custom" else (rec.anthropic_model or "claude-3-5-haiku-20241022")
            elif rec.ai_provider == "google":
                rec.model_name = rec.custom_model_name if rec.google_model == "custom" else (rec.google_model or "gemini-2.5-flash")
            else:
                rec.model_name = rec.custom_model_name or ""
    max_tokens = fields.Integer(
        "Max Response Tokens",
        default=1500,
        help="Maximum tokens in a single AI response. Higher = more detailed but costs more.",
    )
    temperature = fields.Float(
        "Temperature",
        default=0.3,
        help="0.0 = very focused/deterministic  |  1.0 = balanced  |  2.0 = very creative",
    )

    # ── Chat Behaviour ────────────────────────────────────────────────────
    max_history_messages = fields.Integer(
        "Chat History Depth",
        default=10,
        help="Number of previous messages sent to AI as conversation context.",
    )
    analysis_days = fields.Integer(
        "Default Analysis Window (days)",
        default=365,
        help="Days of historical sales data automatically injected into every AI request.",
    )
    top_products_count = fields.Integer(
        "Top Products in Context",
        default=10,
        help="How many top products to include in the AI's sales data context.",
    )

    # ── Custom Prompt ─────────────────────────────────────────────────────
    custom_instructions = fields.Text(
        "Additional AI Instructions",
        help=(
            "Append extra rules to the AI system prompt. "
            "Example: 'Focus on the FMCG category when giving recommendations.'"
        ),
    )

    # ── Insight Scheduler ─────────────────────────────────────────────────
    auto_insights_enabled = fields.Boolean(
        "Auto-Generate Weekly Insights", default=True
    )
    insights_email_notify = fields.Boolean(
        "Email Insights to Sales Manager", default=False
    )
    insights_recipient_ids = fields.Many2many(
        "res.users",
        "ai_config_insight_recipient_rel",
        "config_id",
        "user_id",
        string="Insight Recipients",
    )

    # ── Constraints ───────────────────────────────────────────────────────
    @api.constrains("temperature")
    def _check_temperature(self):
        for rec in self:
            if not 0.0 <= rec.temperature <= 2.0:
                raise ValidationError(_("Temperature must be between 0.0 and 2.0."))

    @api.constrains("max_tokens")
    def _check_max_tokens(self):
        for rec in self:
            if rec.max_tokens < 100 or rec.max_tokens > 8000:
                raise ValidationError(_("Max Response Tokens must be between 100 and 8000."))

    # ── Helpers ───────────────────────────────────────────────────────────
    def get_active_config(self):
        """Return the active config for the current company."""
        config = self.search(
            [("active", "=", True), ("company_id", "=", self.env.company.id)], limit=1
        )
        if not config:
            config = self.search([("active", "=", True)], limit=1)
        return config

    def mask_api_key(self):
        self.ensure_one()
        key = self.api_key or ""
        if len(key) > 8:
            return key[:4] + "*" * (len(key) - 8) + key[-4:]
        return "****"
