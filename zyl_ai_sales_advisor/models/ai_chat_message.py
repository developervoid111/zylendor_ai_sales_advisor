# -*- coding: utf-8 -*-
###############################################################################
#  Chat Message — individual turn within a session
###############################################################################
from odoo import models, fields


class ZylAIChatMessage(models.Model):
    _name = "zyl.ai.chat.message"
    _description = "AI Sales Advisor Chat Message"
    _order = "create_date asc"

    session_id = fields.Many2one(
        "zyl.ai.chat.session",
        "Session",
        required=True,
        ondelete="cascade",
        index=True,
    )
    role = fields.Selection(
        [
            ("system", "System"),
            ("user", "User"),
            ("assistant", "AI Advisor"),
        ],
        required=True,
        default="user",
        string="Role",
    )
    content = fields.Text("Content", required=True)
    tokens_used = fields.Integer("Tokens Used", default=0)
    is_error = fields.Boolean("Error Response", default=False)
    # Feedback
    rating = fields.Selection(
        [("thumbs_up", "Helpful"), ("thumbs_down", "Not Helpful")],
        string="Feedback",
    )
