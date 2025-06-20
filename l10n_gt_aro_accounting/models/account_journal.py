from odoo import models, fields, api


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    establishment_name = fields.Char(
        string="Establishment Name",
        default="",
        help="Name of the establishment associated with this journal"
    )
