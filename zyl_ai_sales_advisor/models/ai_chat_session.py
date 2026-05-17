# -*- coding: utf-8 -*-
###############################################################################
#  Chat Session — one session per conversation thread
###############################################################################
from odoo import models, fields, api, _
from datetime import datetime, timedelta


class ZylAIChatSession(models.Model):
    _name = "zyl.ai.chat.session"
    _description = "AI Sales Advisor Chat Session"
    _rec_name = "name"
    _order = "create_date desc"

    name = fields.Char("Session Title", required=True, default="New Sales Chat")
    user_id = fields.Many2one(
        "res.users", "Started By", default=lambda self: self.env.user, readonly=True
    )
    company_id = fields.Many2one(
        "res.company", "Company", default=lambda self: self.env.company
    )
    message_ids = fields.One2many(
        "zyl.ai.chat.message", "session_id", "Messages"
    )
    message_count = fields.Integer("Message Count", compute="_compute_message_count")
    total_tokens = fields.Integer(
        "Total Tokens Used", compute="_compute_total_tokens", store=True
    )
    state = fields.Selection(
        [("active", "Active"), ("archived", "Archived")],
        default="active",
        string="State",
    )
    last_message_date = fields.Datetime(
        "Last Activity", compute="_compute_last_message_date", store=True
    )
    # Context filters used during this session
    context_date_from = fields.Date("Analysis From")
    context_date_to = fields.Date("Analysis To")

    # ── Computed ──────────────────────────────────────────────────────────
    @api.depends("message_ids")
    def _compute_message_count(self):
        for rec in self:
            rec.message_count = len(rec.message_ids)

    @api.depends("message_ids.tokens_used")
    def _compute_total_tokens(self):
        for rec in self:
            rec.total_tokens = sum(rec.message_ids.mapped("tokens_used"))

    @api.depends("message_ids.create_date")
    def _compute_last_message_date(self):
        for rec in self:
            dates = rec.message_ids.mapped("create_date")
            rec.last_message_date = max(dates) if dates else rec.create_date

    # ── Methods ───────────────────────────────────────────────────────────
    def get_history_for_ai(self, max_messages=10):
        """Return the last N user/assistant messages formatted for the AI API."""
        self.ensure_one()
        messages = (
            self.message_ids.filtered(lambda m: m.role in ("user", "assistant"))
            .sorted("create_date")[-max_messages:]
        )
        return [{"role": m.role, "content": m.content} for m in messages]

    def add_message(self, role, content, tokens_used=0):
        self.ensure_one()
        return self.env["zyl.ai.chat.message"].create(
            {
                "session_id": self.id,
                "role": role,
                "content": content,
                "tokens_used": tokens_used,
            }
        )

    @api.model
    def cleanup_old_sessions(self, days=90):
        """Cron: archive sessions older than `days` with no recent activity."""
        cutoff = datetime.now() - timedelta(days=days)
        old_sessions = self.search(
            [("last_message_date", "<", cutoff), ("state", "=", "active")]
        )
        old_sessions.write({"state": "archived"})
